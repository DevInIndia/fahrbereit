"""A2UI surface for live agent progress. The second half of M-4.

This surface is built incrementally on purpose. The catalogue can afford to be sent
whole because it arrives once at the end of a turn; progress cannot, because the whole
point is that it changes while the user waits. So every update here is an
`updateComponents` carrying only the component that actually changed, which is what
FR-034 asks for and what makes the surface a live instrument rather than a summary
printed after the fact.

Component ids are stable for the life of a session, so the renderer updates a node in
place instead of tearing the tree down.
"""

from __future__ import annotations

from typing import Any, Optional

from agent import i18n
from agent.i18n import DEFAULT_LANG, Lang
from agent.state import InterviewState, Phase
from agent.tools.ranking import FilterReport, constraint_label

SURFACE_ID = "fahrbereit-fortschritt"
CATALOG_ID = "fahrbereit/v1"

# The phases a turn moves through, in order. The interface draws them as a track, so
# the order here is the order on screen.
PHASEN: tuple[Phase, ...] = (
    Phase.INTERVIEW,
    Phase.SUCHE,
    Phase.BEWERTUNG,
    Phase.EMPFEHLUNG,
)

PHASE_LABEL: dict[Phase, dict[str, str]] = {
    Phase.INTERVIEW: {"de": "Interview", "en": "Interview"},
    Phase.SUCHE: {"de": "Suche", "en": "Search"},
    Phase.BEWERTUNG: {"de": "Bewertung", "en": "Scoring"},
    Phase.EMPFEHLUNG: {"de": "Empfehlung", "en": "Recommendation"},
}

# Which phase a tool call represents. The agent does not announce its phase; it calls
# tools, and the phase follows from which tool.
TOOL_PHASE: dict[str, Phase] = {
    "interview_merken": Phase.INTERVIEW,
    "interview_stand": Phase.INTERVIEW,
    "empfehlungen_erstellen": Phase.SUCHE,
}

TOOL_LABEL: dict[str, dict[str, str]] = {
    "interview_merken": {"de": "Angaben übernehmen", "en": "Recording answers"},
    "interview_stand": {"de": "Bekanntes prüfen", "en": "Checking what is known"},
    "empfehlungen_erstellen": {"de": "Bestand filtern und bewerten", "en": "Filtering and scoring"},
}


def _component(component_id: str, name: str, props: dict[str, Any]) -> dict[str, Any]:
    return {"id": component_id, "component": name, **props}


def _msg(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"version": "v0.9", kind: payload}


def _update(components: list[dict[str, Any]]) -> dict[str, Any]:
    """One incremental update. Only the components named here are touched."""
    return _msg("updateComponents", {"surfaceId": SURFACE_ID, "components": components})


# ------------------------------------------------------------------ pieces


def phasen_component(aktuell: Phase, lang: Lang = DEFAULT_LANG) -> dict[str, Any]:
    reached = False
    phasen = []
    for phase in PHASEN:
        ist_aktiv = phase is aktuell
        if ist_aktiv:
            reached = True
        phasen.append(
            {
                "name": phase.value,
                "label": PHASE_LABEL[phase][lang],
                "aktiv": ist_aktiv,
                "erledigt": not reached and not ist_aktiv,
            }
        )
    return _component("phase", "PhasenAnzeige", {"phasen": phasen})


def slots_component(state: InterviewState, lang: Lang = DEFAULT_LANG) -> dict[str, Any]:
    """The interview checklist. Inferred values are marked so they can be corrected."""
    from agent.server import _interview_payload  # built once, reused here

    zeilen = [
        {
            "label": row["label"],
            "wert": row["wert"],
            "herkunft": row["herkunft"] or "",
            "offen": row["offen"],
            "zuBestaetigen": row["herkunft"] == "inferred" and not row["bestaetigt"],
        }
        for row in _interview_payload(state, lang)
    ]
    gefuellt = sum(1 for z in zeilen if not z["offen"])
    return _component(
        "slots",
        "SlotCheckliste",
        {
            "zeilen": zeilen,
            "gefuellt": gefuellt,
            "gesamt": len(zeilen),
            "hinweis": (
                "Abgeleitete Werte sind markiert und korrigierbar."
                if lang == "de"
                else "Inferred values are marked and can be corrected."
            ),
        },
    )


def suche_component(
    report: Optional[FilterReport], lang: Lang = DEFAULT_LANG, laeuft: bool = False
) -> dict[str, Any]:
    if report is None:
        return _component(
            "suche",
            "SuchStatus",
            {
                "aktiv": laeuft,
                "gesamt": 0,
                "uebrig": 0,
                "ausgeschlossen": [],
                "hinweis": (
                    "Noch nicht gesucht." if lang == "de" else "No search yet."
                ),
            },
        )
    return _component(
        "suche",
        "SuchStatus",
        {
            "aktiv": laeuft,
            "gesamt": report.gesamt,
            "uebrig": report.uebrig,
            "ausgeschlossen": [
                {"grund": constraint_label(key, lang), "anzahl": count}
                for key, count in report.ausgeschlossen.items()
            ],
            "hinweis": "",
        },
    )


def strom_component(schritte: list[dict[str, Any]], lang: Lang = DEFAULT_LANG) -> dict[str, Any]:
    return _component(
        "strom",
        "WerkzeugStrom",
        {
            "schritte": schritte,
            "titel": "Werkzeugaufrufe" if lang == "de" else "Tool calls",
        },
    )


def tool_label(name: str, lang: Lang = DEFAULT_LANG) -> str:
    return TOOL_LABEL.get(name, {}).get(lang, name)


# ------------------------------------------------------------------ messages


def initial_messages(
    state: InterviewState, lang: Lang = DEFAULT_LANG
) -> list[dict[str, Any]]:
    """Create the surface and lay out its four panels. Sent once per session."""
    kopf = _component(
        "fortschritt-kopf",
        "Kopfzeile",
        {
            "titel": "Agent" if lang == "de" else "Agent",
            "untertitel": (
                "Was der Agent gerade tut, während er es tut."
                if lang == "de"
                else "What the agent is doing, while it does it."
            ),
        },
    )
    root = _component(
        "root",
        "Spalte",
        {"kinder": ["fortschritt-kopf", "phase", "slots", "suche", "strom"]},
    )
    return [
        _msg("createSurface", {"surfaceId": SURFACE_ID, "catalogId": CATALOG_ID}),
        _update(
            [
                kopf,
                phasen_component(state.phase, lang),
                slots_component(state, lang),
                suche_component(None, lang),
                strom_component([], lang),
                root,
            ]
        ),
    ]


def phase_message(phase: Phase, lang: Lang = DEFAULT_LANG) -> dict[str, Any]:
    """Only the phase track. Nothing else on the surface is touched."""
    return _update([phasen_component(phase, lang)])


def slots_message(state: InterviewState, lang: Lang = DEFAULT_LANG) -> dict[str, Any]:
    return _update([slots_component(state, lang)])


def suche_message(
    report: Optional[FilterReport], lang: Lang = DEFAULT_LANG, laeuft: bool = False
) -> dict[str, Any]:
    return _update([suche_component(report, lang, laeuft)])


def strom_message(
    schritte: list[dict[str, Any]], lang: Lang = DEFAULT_LANG
) -> dict[str, Any]:
    return _update([strom_component(schritte, lang)])
