"""HTTP surface for the fahrbereit client.

Two responsibilities, both thin:

1. Serve the A2UI catalogue surface, built from the ranking engine. No ranking,
   scoring or cost arithmetic happens here.
2. Host the MCP App bridge. Spike A established that we hold our own MCP client to
   the formular and kasse servers, fetch the `ui://` resource and hand the HTML to
   the client, which renders it in a sandboxed iframe. See docs/spike-notes.md.

The agent loop attaches later. This layer exists so the surfaces can be seen and
driven before the model is in the path.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent import i18n
from agent import mcp_client
from agent import observability
from agent.model import install_cache_if_enabled
from agent.state import (
    Budget,
    Dimension,
    HardConstraints,
    Intent,
    InterviewState,
    Location,
    UseCaseTag,
    tags_from_text,
)
from agent.session import ranking_for, run_turn, state_for
from agent.streaming import stream_turn
from agent.store import STORE
from agent.surfaces.katalog import build_messages, build_weight_update
from agent.tools.ranking import rank
from agent.tools.tco import tco_for_state
from mcpapps.formular.server import render_for as render_formular
from mcpapps.kasse.server import build_order, kasse_bestaetigen
from mcpapps.kasse.server import render_for as render_kasse

app = FastAPI(title="fahrbereit")

# Development response cache, keyed on prompt hash. Off unless MODEL_CACHE=1, so a
# demonstration never shows a cached answer to a question that was not asked.
CACHE_AKTIV = install_cache_if_enabled()

# Tracing first, because Langfuse registers the OpenTelemetry tracer provider that
# the LangChain instrumentor emits into. Absent keys disable it and change nothing.
TRACING_AKTIV = observability.configure()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # local development only; the container serves same origin
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------ personas

def _familie() -> InterviewState:
    text = (
        "Ich fahre meine zwei Kinder zur Schule und einmal im Monat 300 km zu meinen "
        "Eltern. Budget etwa 25.000 Euro."
    )
    st = InterviewState(session_id="demo-familie")
    st.intent = st.intent.state(Intent.KAUF)
    st.use_case_text = st.use_case_text.state(text)
    st.use_case_tags = st.use_case_tags.infer(
        tags_from_text(text) + [UseCaseTag.LANGSTRECKE], confidence=0.8
    )
    st.budget = st.budget.state(Budget(max_kaufpreis_eur=25_000))
    st.jahresfahrleistung_km = st.jahresfahrleistung_km.infer(15_000, confidence=0.6)
    st.constraints_hard = st.constraints_hard.state(
        HardConstraints(
            min_sitzplaetze=5, min_kofferraum_liter=400,
            unfallfrei_erforderlich=True, umweltplakette="grün",
        )
    )
    st.location = st.location.state(Location(plz="80339", ort="München"))
    return st


def _pendler() -> InterviewState:
    text = "Ich pendle jeden Tag 45 km in die Stadt zur Arbeit. Automatik bitte."
    st = InterviewState(session_id="demo-pendler")
    st.intent = st.intent.state(Intent.KAUF)
    st.use_case_text = st.use_case_text.state(text)
    st.use_case_tags = st.use_case_tags.infer(tags_from_text(text), confidence=0.85)
    st.budget = st.budget.state(Budget(max_kaufpreis_eur=32_000))
    st.jahresfahrleistung_km = st.jahresfahrleistung_km.state(22_000)
    st.constraints_hard = st.constraints_hard.state(
        HardConstraints(getriebe="Automatik", umweltplakette="grün", unfallfrei_erforderlich=True)
    )
    st.location = st.location.state(Location(plz="10115", ort="Berlin", max_entfernung_km=300))
    return st


def _umzug() -> InterviewState:
    text = "Ich brauche für ein Wochenende ein Auto für einen Umzug."
    st = InterviewState(session_id="demo-umzug")
    st.intent = st.intent.state(Intent.MIETE)
    st.use_case_text = st.use_case_text.state(text)
    st.use_case_tags = st.use_case_tags.infer(tags_from_text(text), confidence=0.9)
    st.budget = st.budget.state(Budget(max_tagessatz_eur=95))
    # "für ein Wochenende" is the user's own words, so the duration is stated.
    st.mietdauer_tage = st.mietdauer_tage.state(3, source="für ein Wochenende")
    st.constraints_hard = st.constraints_hard.state(HardConstraints(min_kofferraum_liter=350))
    st.location = st.location.state(Location(plz="20095", ort="Hamburg"))
    return st


PERSONAS = {"familie": _familie, "pendler": _pendler, "umzug": _umzug}


class ChatRequest(BaseModel):
    session_id: str = "default"
    nachricht: str
    lang: str = "de"


class WeightRequest(BaseModel):
    persona: str = "familie"
    gewichte: dict[str, float] | None = None
    limit: int = 6
    lang: str = "de"


# ------------------------------------------------------------------ routes


@app.get("/api/health")
def health() -> dict[str, Any]:
    from agent.listing import load_listings

    return {
        "status": "ok",
        "listings": len(load_listings()),
        "personas": sorted(PERSONAS),
        "langs": list(i18n.LANGS),
        "payment_provider": os.environ.get("PAYMENT_PROVIDER", "mock"),
        "mcp": mcp_client.mode(),
        "tracing": observability.status(),
        "mcp_fehler": mcp_client.last_error(),
        "simuliert": True,
    }


@app.get("/api/personas")
def personas() -> list[dict[str, str]]:
    out = []
    for name, factory in PERSONAS.items():
        st = factory()
        out.append(
            {
                "id": name,
                "beschreibung": st.use_case_text.value or "",
                "intent": st.effective_intent().value,
            }
        )
    return out


@app.post("/api/surface/katalog")
def katalog(req: WeightRequest) -> dict[str, Any]:
    """The A2UI catalogue surface, built from the ranking engine."""
    factory = PERSONAS.get(req.persona)
    if factory is None:
        raise HTTPException(404, f"Unbekannte Persona {req.persona!r}")

    state = factory()
    if req.gewichte:
        unknown = set(req.gewichte) - {d.value for d in Dimension}
        if unknown:
            raise HTTPException(400, f"Unbekannte Dimensionen: {sorted(unknown)}")
        state.preferences_soft = state.preferences_soft.state(req.gewichte)

    lang = i18n.normalise(req.lang)
    result = rank(state, limit=req.limit, tco_fn=tco_for_state, lang=lang)

    return {
        "messages": build_messages(result, lang=lang),
        "interview": _interview_payload(state, lang),
        "gewichte": result.gewichte,
        "lang": lang,
    }


@app.post("/api/surface/gewichte")
def gewichte(req: WeightRequest) -> dict[str, Any]:
    """Weights only, as an incremental data model update. FR-034."""
    factory = PERSONAS.get(req.persona)
    if factory is None:
        raise HTTPException(404, f"Unbekannte Persona {req.persona!r}")
    state = factory()
    if req.gewichte:
        state.preferences_soft = state.preferences_soft.state(req.gewichte)
    lang = i18n.normalise(req.lang)
    result = rank(state, limit=req.limit, tco_fn=tco_for_state, lang=lang)
    return {"messages": build_weight_update(result, lang), "lang": lang}


def _interview_payload(
    state: InterviewState, lang: str = "de"
) -> list[dict[str, Any]]:
    """The slot checklist, with inferred values marked. Feeds the progress panel.

    Slot names and their values are internal identifiers, so they are translated here
    rather than shipped raw. A user should never be shown `jahresfahrleistung_km` or
    `min_sitzplaetze` in either language.
    """
    norm = i18n.normalise(lang)

    def wert_text(name: str, value: Any) -> str:
        if value is None:
            return ""
        if name == "intent":
            return i18n.t(f"intent.{getattr(value, 'value', value)}", norm)
        if name == "use_case_tags":
            return ", ".join(
                i18n.t(f"tag.{getattr(v, 'value', v)}", norm) for v in value
            )
        if isinstance(value, list):
            return ", ".join(str(getattr(v, "value", v)) for v in value)
        if hasattr(value, "model_dump"):
            teile = []
            for key, inner in value.model_dump().items():
                if inner in (None, False):
                    continue
                label = i18n.t(f"f.{key}", norm)
                if inner is True:
                    teile.append(label)
                elif key == "umweltplakette":
                    teile.append(f"{label}: {i18n.plakette(str(inner), norm)}")
                elif isinstance(inner, int) and key.endswith("_eur"):
                    teile.append(f"{label}: {i18n.fmt_int(inner, norm)} EUR")
                elif isinstance(inner, int) and key.endswith("_liter"):
                    teile.append(f"{label}: {i18n.fmt_int(inner, norm)} l")
                elif isinstance(inner, int) and key.endswith("_km"):
                    teile.append(f"{label}: {i18n.fmt_int(inner, norm)} km")
                elif isinstance(inner, list):
                    teile.append(
                        f"{label}: "
                        + ", ".join(i18n.kraftstoff(str(x), norm) for x in inner)
                        if key == "kraftstoff"
                        else f"{label}: {', '.join(str(x) for x in inner)}"
                    )
                else:
                    teile.append(f"{label}: {inner}")
            return ", ".join(teile)
        if name == "jahresfahrleistung_km":
            return f"{i18n.fmt_int(value, norm)} km"
        if name == "mietdauer_tage":
            einheit = "Tage" if norm == "de" else "days"
            return f"{i18n.fmt_int(value, norm)} {einheit}"
        if isinstance(value, int):
            return i18n.fmt_int(value, norm)
        return str(getattr(value, "value", value))

    # Two slots are specific to one intent and are noise under the other. Showing a
    # buyer an open "Rental duration" row invites them to answer a question that does
    # not apply to them.
    nur_miete = {"mietdauer_tage"}
    nur_kauf = {"jahresfahrleistung_km"}
    ist_miete = state.effective_intent() is Intent.MIETE

    rows = []
    for name in state.slot_names():
        if name in nur_miete and not ist_miete:
            continue
        if name in nur_kauf and ist_miete:
            continue
        slot = state.slot(name)
        rows.append(
            {
                "slot": name,
                "label": i18n.t(f"slot.{name}", norm),
                "wert": wert_text(name, slot.value),
                "herkunft": slot.provenance.value if slot.provenance else None,
                "bestaetigt": slot.confirmed,
                "offen": not slot.is_set,
            }
        )
    return rows


# ------------------------------------------------------------------ agent


@app.post("/api/chat")
def chat(req: ChatRequest) -> dict[str, Any]:
    """One conversational turn. This is the multistep agent, M-1.

    The agent fills the interview record, decides when it has enough, and calls the
    ranking engine as a tool. Nothing here ranks, scores or invents; when a ranking
    exists it is translated into A2UI messages and returned alongside the reply.
    """
    if not req.nachricht.strip():
        raise HTTPException(400, "Leere Nachricht")

    lang = i18n.normalise(req.lang)
    turn = run_turn(req.session_id, req.nachricht.strip(), lang)

    result = ranking_for(req.session_id)
    messages = build_messages(result, lang=lang) if result else None
    state = state_for(req.session_id)

    return {
        "antwort": turn.antwort,
        "werkzeuge": turn.werkzeuge,
        "modellaufrufe": turn.modellaufrufe,
        "gedrosselt": turn.gedrosselt,
        "messages": messages,
        "interview": _interview_payload(state, lang),
        "lang": lang,
    }


@app.post("/api/chat/stream")
def chat_stream(req: ChatRequest) -> StreamingResponse:
    """One conversational turn, streamed.

    Emits phase changes, tool calls and filter counts as they happen, each as an
    incremental A2UI update to the progress surface, then the reply and the catalogue
    at the end. No extra model calls: everything streamed here is already known
    server side at the moment it occurs.
    """
    if not req.nachricht.strip():
        raise HTTPException(400, "Leere Nachricht")

    return StreamingResponse(
        stream_turn(req.session_id, req.nachricht.strip(), req.lang),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # nginx buffers proxied responses by default, which would hold every
            # event back until the turn finished and defeat the point.
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/chat/reset")
def chat_reset(req: ChatRequest) -> dict[str, Any]:
    """Start over. Clears the interview record for this session."""
    STORE.clear(req.session_id)
    return {"status": "ok", "session_id": req.session_id}


# ------------------------------------------------------------------ MCP Apps


@app.get("/api/app/formular")
def app_formular(
    listing_id: str = "FB-00001",
    intent: str = "kauf",
    fahrzeug: str = "",
    lang: str = "de",
) -> dict:
    """The formular MCP App surface, fetched from its MCP server."""
    uri, html = mcp_client.surface_html(
        "formular",
        {
            "listing_id": listing_id,
            "intent": intent,
            "fahrzeug": fahrzeug or listing_id,
            "lang": i18n.normalise(lang),
        },
    )
    return {
        "resourceUri": uri,
        "mimeType": "text/html;profile=mcp-app",
        "html": html,
        "quelle": mcp_client.mode(),
    }


@app.get("/api/app/kasse")
def app_kasse(
    listing_id: str = "FB-00001",
    fahrzeug: str = "",
    intent: str = "kauf",
    betrag_eur: int = 0,
    lang: str = "de",
) -> dict:
    """The kasse MCP App surface, fetched from its MCP server. Simulated throughout."""
    norm = i18n.normalise(lang)
    uri, html = mcp_client.surface_html(
        "kasse",
        {
            "listing_id": listing_id,
            "fahrzeug": fahrzeug or listing_id,
            "intent": intent,
            "betrag_eur": betrag_eur,
            "kaution_eur": 500 if intent == "miete" else 0,
            "abholort": "Hamburg" if intent == "miete" else "",
            "zeitraum": (
                ("12. bis 14. September" if norm == "de" else "12 to 14 September")
                if intent == "miete"
                else ""
            ),
            "lang": norm,
        },
    )
    return {
        "resourceUri": uri,
        "mimeType": "text/html;profile=mcp-app",
        "html": html,
        "quelle": mcp_client.mode(),
    }


class BridgeCall(BaseModel):
    """A tool call proxied from inside a sandboxed app iframe."""

    tool: str
    args: dict[str, Any] = {}


@app.post("/api/app/bridge")
def app_bridge(call: BridgeCall) -> dict[str, Any]:
    """The app bridge, hosted here rather than by the AG-UI middleware.

    Only tools a surface is allowed to reach are routed. Anything else is refused, so
    a sandboxed iframe cannot use the bridge as a general remote procedure call.
    """
    if call.tool not in mcp_client.TOOL_OWNER:
        raise HTTPException(404, f"Unbekanntes Werkzeug {call.tool!r}")
    try:
        return {"result": mcp_client.call_tool(call.tool, call.args)}
    except KeyError:
        raise HTTPException(404, f"Unbekanntes Werkzeug {call.tool!r}") from None


class LiveMarketCheckRequest(BaseModel):
    marke: str
    modell: str
    variante: str
    baujahr: int | None = None
    kilometerstand_km: int | None = None
    preis_eur: int


@app.post("/api/live-market-check")
def live_market_check(req: LiveMarketCheckRequest) -> dict[str, Any]:
    """Isolated live market check using Gemini Search Grounding.

    Display-only validation. Does not affect ranking scores.
    """
    from agent.live_check import perform_live_market_check

    return perform_live_market_check(
        req.marke,
        req.modell,
        req.variante,
        req.baujahr,
        req.kilometerstand_km,
        req.preis_eur,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

