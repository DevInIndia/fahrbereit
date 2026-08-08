"""Tracing to Langfuse over OpenTelemetry. The bonus requirement.

Generic LLM tracing is easy and not very interesting: it shows that a model was
called and what it said. The thing worth tracing here is the part the model does not
do. This project's whole claim is that recommendations come from deterministic
Python, so a trace has to let someone follow a recommendation back to the exact
filter counts, weights and per dimension contributions that produced it. That is
FR-035, and it is what `record_ranking` below exists for.

Setup order matters. Langfuse builds an OpenTelemetry TracerProvider and registers it
globally, and the OpenInference LangChain instrumentor emits into whatever provider is
current. So the Langfuse client is constructed first and the instrumentor attached
afterwards; reversing that sends every span into a no-op provider and produces silence
that looks exactly like success.

Absent keys disable tracing and change nothing else. Observability is a bonus and must
never be able to take the product down.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

log = logging.getLogger("fahrbereit.observability")

_ENABLED = False
_CLIENT: Optional[Any] = None
_STATUS = "nicht konfiguriert"


def _setting(*names: str) -> str:
    """First non-empty value among these variable names.

    Both LANGFUSE_HOST and LANGFUSE_BASE_URL are accepted because the SDK names one
    and the dashboard documents the other, and a reader should not have to guess.
    """
    for name in names:
        value = os.environ.get(name, "").strip()
        # Quotes pasted from a dashboard would otherwise become part of the value.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if value:
            return value
    return ""


def configure() -> bool:
    """Turn on tracing if credentials are present. Safe to call more than once."""
    global _ENABLED, _CLIENT, _STATUS

    if _ENABLED:
        return True

    public_key = _setting("LANGFUSE_PUBLIC_KEY")
    secret_key = _setting("LANGFUSE_SECRET_KEY")
    host = _setting("LANGFUSE_HOST", "LANGFUSE_BASE_URL") or "https://cloud.langfuse.com"

    if not public_key or not secret_key:
        _STATUS = "keine Langfuse-Schlüssel gesetzt"
        log.info("Langfuse tracing off: no keys configured.")
        return False

    try:
        from langfuse import Langfuse

        # Constructing the client registers the global tracer provider.
        _CLIENT = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
            environment=os.environ.get("FAHRBEREIT_ENV", "development"),
            release=os.environ.get("FAHRBEREIT_RELEASE", "milestone-4"),
        )

        if not _CLIENT.auth_check():
            _STATUS = "Langfuse lehnt die Schlüssel ab"
            log.error("Langfuse rejected the credentials. Tracing stays off.")
            _CLIENT = None
            return False

        # Attached after the client, so it emits into Langfuse's provider.
        from openinference.instrumentation.langchain import LangChainInstrumentor

        LangChainInstrumentor().instrument()

        _ENABLED = True
        _STATUS = f"aktiv gegen {host}"
        log.info("Langfuse tracing active against %s", host)
        return True

    except Exception as exc:  # noqa: BLE001
        # Tracing is a bonus. It must never be able to break the product.
        _STATUS = f"Fehler beim Start: {exc}"
        log.warning("Langfuse tracing could not start: %s", exc)
        _CLIENT = None
        return False


def enabled() -> bool:
    return _ENABLED


def status() -> str:
    """Human readable state, for /api/health. Never includes a credential."""
    return _STATUS


def _span():
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        return span if span and span.is_recording() else None
    except Exception:  # noqa: BLE001
        return None


def record_ranking(state, result, lang: str = "de") -> None:
    """Record the ranking's inputs and outputs as their own observation. FR-035.

    This is the observability that earns its keep. Generic tracing shows that a model
    was called; this shows the filter counts, the weight vector and the per dimension
    contributions that actually decided the recommendation, so a reader can follow a
    car back to the arithmetic that chose it.

    It creates its own observation rather than annotating the ambient span. Setting
    attributes on `get_current_span()` inside a tool body silently did nothing: the
    instrumentor builds its tool span from callbacks, so it is not the current span
    while the tool runs, and the attributes went to a non-recording span. An explicit
    observation cannot fail that way.
    """
    if not _ENABLED or _CLIENT is None:
        return

    try:
        budget = state.budget.value
        constraints = state.constraints_hard.value
        report = result.report

        eingabe = {
            "intent": state.effective_intent().value,
            "sprache": lang,
            "budget_max_eur": (
                budget.ceiling_for(state.effective_intent()) if budget else None
            ),
            "einsatzzweck": [t.value for t in (state.use_case_tags.value or [])],
            "harte_kriterien": (
                {k: v for k, v in constraints.model_dump().items() if v not in (None, False)}
                if constraints
                else {}
            ),
            "gewichte": {k: round(v, 4) for k, v in result.gewichte.items()},
        }

        ausgabe = {
            "filter": {
                "geprueft": report.gesamt,
                "verblieben": report.uebrig,
                "ausgeschlossen": dict(report.ausgeschlossen),
            },
            "empfehlungen": [
                {
                    "rang": r.rang,
                    "id": r.listing.id,
                    "fahrzeug": r.listing.bezeichnung,
                    "punkte": round(r.score.total, 2),
                    "preis_eur": r.listing.preis_referenz(),
                    "tco_5j_eur": r.tco_gesamt_eur,
                }
                for r in result.empfehlungen
            ],
        }

        if result.empfehlungen:
            winner = result.empfehlungen[0]
            ausgabe["gewinner_begruendung"] = {
                d.name.value: {
                    "gewicht": round(d.gewicht, 4),
                    "rang_im_feld": round(d.rohwert, 2),
                    "beitrag": round(d.beitrag, 4),
                    "begrenzt_durch": d.begrenzt_durch,
                }
                for d in winner.score.dimensionen
            }
            # The identity a reader can check by hand.
            ausgabe["gewinner_summe_beitraege"] = round(
                sum(d.beitrag for d in winner.score.dimensionen), 2
            )
            ausgabe["gewinner_punkte"] = round(winner.score.total, 2)

        with _CLIENT.start_as_current_observation(
            name="fahrbereit.ranking",
            as_type="span",
            input=eingabe,
            output=ausgabe,
            metadata={
                "deterministisch": True,
                "hinweis": (
                    "Filter, Bewertung und Gesamtkosten stammen aus Python, nicht aus "
                    "dem Modell. Das Modell erzaehlt diese Zahlen nur."
                ),
            },
        ):
            pass

    except Exception as exc:  # noqa: BLE001
        log.debug("could not record ranking: %s", exc)


from contextlib import contextmanager


@contextmanager
def turn_span(session_id: str, nachricht: str, lang: str):
    """Wrap one user turn in a root observation.

    Without this every LangChain run became its own trace: the dashboard filled with
    orphan spans and no single view showed a turn end to end. A root observation gives
    the model calls, the tool calls and the ranking attributes one parent.

    A no-op when tracing is off, so the caller needs no branch.
    """
    if not _ENABLED or _CLIENT is None:
        yield None
        return
    try:
        with _CLIENT.start_as_current_observation(
            name="fahrbereit.turn",
            as_type="agent",
            input={"nachricht": nachricht, "lang": lang},
            metadata={"session_id": session_id, "lang": lang},
        ) as span:
            yield span
    except Exception as exc:  # noqa: BLE001
        log.debug("turn span failed: %s", exc)
        yield None


def record_turn(session_id: str, nachricht: str, lang: str) -> None:
    """Mark the current span with who asked and in which language."""
    if not _ENABLED:
        return
    span = _span()
    if span is None:
        return
    try:
        span.set_attribute("fahrbereit.session_id", session_id)
        span.set_attribute("fahrbereit.lang", lang)
        span.set_attribute("fahrbereit.user_message_chars", len(nachricht))
    except Exception:  # noqa: BLE001
        pass


def flush() -> None:
    """Send anything buffered. Called before a process exits or after an eval run."""
    if _CLIENT is not None:
        try:
            _CLIENT.flush()
        except Exception:  # noqa: BLE001
            pass


def client():
    return _CLIENT
