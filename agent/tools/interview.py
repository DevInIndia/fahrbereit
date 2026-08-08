"""The tools the agent may call.

Three of them, deliberately. The agent records what it learns, checks what it already
knows so it never asks twice, and asks the ranking engine for results. It computes
nothing: `empfehlungen_erstellen` calls the same `rank` and `cost_of_ownership` the
terminal demo calls, and hands back ready-made justifications for the model to quote.

Tool results are kept compact. Every token returned here is a token charged against a
500 request daily budget, so the tools return what is needed to narrate and no more.
The full detail goes to the interface through the A2UI surface, not through the model.
"""

from __future__ import annotations

from typing import Optional

from langchain_core.tools import tool

from agent import i18n, observability
from agent.state import (
    Budget,
    HardConstraints,
    Intent,
    Location,
    Provenance,
    UseCaseTag,
    tags_from_text,
)
from agent.store import CURRENT_SESSION, STORE, current_state, save_state
from agent.tools.ranking import constraint_label, rank
from agent.tools.tco import STANDARD_MIETDAUER_TAGE, tco_for_state

HERKUNFT = {"gesagt": "stated", "abgeleitet": "inferred"}


def _apply(state, name: str, value, herkunft: str, quelle: str | None) -> None:
    slot = state.slot(name)
    if HERKUNFT.get(herkunft) == "inferred":
        setattr(state, name, slot.infer(value, confidence=0.75, source=quelle))
    else:
        setattr(state, name, slot.state(value, source=quelle))


def _composite(state, name: str, factory, updates: dict, herkunft: str):
    """Merge fields into a composite slot without letting inference overwrite a statement.

    `Slot.infer` already refuses to replace a stated slot, but a composite value is a
    mutable object: mutating it in place before calling infer changed the stated value
    behind the guard's back. So the merge happens on a copy, and when the existing slot
    was stated an inference may only fill fields that are still empty.
    """
    slot = state.slot(name)
    vorhanden = slot.value
    ziel = vorhanden.model_copy(deep=True) if vorhanden is not None else factory()

    ist_ableitung = HERKUNFT.get(herkunft) == "inferred"
    war_gesagt = slot.provenance is Provenance.STATED

    for key, value in updates.items():
        if ist_ableitung and war_gesagt and getattr(ziel, key, None) is not None:
            continue  # an inference never overwrites something the user stated
        setattr(ziel, key, value)
    return ziel


@tool
def interview_merken(
    herkunft: str = "gesagt",
    quelle: Optional[str] = None,
    intent: Optional[str] = None,
    use_case_text: Optional[str] = None,
    use_case_tags: Optional[list[str]] = None,
    kategorien: Optional[list[str]] = None,
    max_kaufpreis_eur: Optional[int] = None,
    max_tagessatz_eur: Optional[int] = None,
    jahresfahrleistung_km: Optional[int] = None,
    mietdauer_tage: Optional[int] = None,
    getriebe: Optional[str] = None,
    kraftstoff: Optional[list[str]] = None,
    min_sitzplaetze: Optional[int] = None,
    min_kofferraum_liter: Optional[int] = None,
    umweltplakette: Optional[str] = None,
    unfallfrei_erforderlich: Optional[bool] = None,
    max_kilometerstand: Optional[int] = None,
    plz: Optional[str] = None,
    ort: Optional[str] = None,
    max_entfernung_km: Optional[int] = None,
) -> str:
    """Record what the user said or what you inferred, into the interview record.

    Set herkunft to "gesagt" when the user stated it, "abgeleitet" when you worked it
    out. Inferred values are shown to the user marked for confirmation. Pass only the
    fields you actually learned; leave everything else out.

    intent is one of: kauf, miete, unentschieden.
    mietdauer_tage is how many days the car is rented for, and applies to miete only.
    getriebe is one of: Schaltgetriebe, Automatik.
    kraftstoff entries: Benzin, Diesel, Elektro, Hybrid, Plug-in-Hybrid.
    umweltplakette is one of: grün, gelb, rot.
    """
    state = current_state()
    geaendert: list[str] = []

    if intent:
        try:
            _apply(state, "intent", Intent(intent.strip().lower()), herkunft, quelle)
            geaendert.append("intent")
        except ValueError:
            return f"intent {intent!r} ist unbekannt. Erlaubt: kauf, miete, unentschieden."

    if use_case_text:
        _apply(state, "use_case_text", use_case_text, herkunft, quelle)
        geaendert.append("use_case_text")
        if not state.use_case_tags.is_set:
            abgeleitet = tags_from_text(use_case_text)
            if abgeleitet:
                state.use_case_tags = state.use_case_tags.infer(
                    abgeleitet, confidence=0.7, source="aus der Beschreibung abgeleitet"
                )
                geaendert.append("use_case_tags")

    if use_case_tags:
        gueltig = []
        for raw in use_case_tags:
            try:
                gueltig.append(UseCaseTag(raw.strip().lower()))
            except ValueError:
                continue
        if gueltig:
            _apply(state, "use_case_tags", gueltig, herkunft, quelle)
            geaendert.append("use_case_tags")

    if kategorien:
        from agent.listing import KATEGORIEN

        treffer = [k for k in kategorien if k in KATEGORIEN]
        if treffer:
            _apply(state, "category_preference", treffer, herkunft, quelle)
            geaendert.append("category_preference")

    budget_updates = {
        k: v
        for k, v in {
            "max_kaufpreis_eur": max_kaufpreis_eur,
            "max_tagessatz_eur": max_tagessatz_eur,
        }.items()
        if v is not None
    }
    if budget_updates:
        budget = _composite(state, "budget", Budget, budget_updates, herkunft)
        _apply(state, "budget", budget, herkunft, quelle)
        geaendert.append("budget")

    if jahresfahrleistung_km:
        _apply(state, "jahresfahrleistung_km", jahresfahrleistung_km, herkunft, quelle)
        geaendert.append("jahresfahrleistung_km")

    if mietdauer_tage:
        _apply(state, "mietdauer_tage", mietdauer_tage, herkunft, quelle)
        geaendert.append("mietdauer_tage")

    constraint_felder = {
        "getriebe": getriebe,
        "kraftstoff": kraftstoff,
        "min_sitzplaetze": min_sitzplaetze,
        "min_kofferraum_liter": min_kofferraum_liter,
        "umweltplakette": umweltplakette,
        "unfallfrei_erforderlich": unfallfrei_erforderlich,
        "max_kilometerstand": max_kilometerstand,
    }
    gesetzt = {k: v for k, v in constraint_felder.items() if v is not None}
    if gesetzt:
        constraints = _composite(
            state, "constraints_hard", HardConstraints, gesetzt, herkunft
        )
        _apply(state, "constraints_hard", constraints, herkunft, quelle)
        geaendert.append("constraints_hard")

    ort_updates = {
        k: v
        for k, v in {"plz": plz, "ort": ort, "max_entfernung_km": max_entfernung_km}.items()
        if v is not None
    }
    if ort_updates:
        location = _composite(state, "location", Location, ort_updates, herkunft)
        _apply(state, "location", location, herkunft, quelle)
        geaendert.append("location")

    if not geaendert:
        return "Nichts übernommen, es wurden keine Angaben mitgegeben."

    save_state(state)
    offen = state.missing_slots()
    return (
        f"Übernommen ({herkunft}): {', '.join(dict.fromkeys(geaendert))}. "
        f"Noch offen: {', '.join(offen) if offen else 'nichts'}."
    )


@tool
def interview_stand() -> str:
    """Show what the interview already knows, so you never ask for it twice.

    Returns each filled slot with its value and whether it was stated or inferred,
    plus the slots still missing and any inference awaiting confirmation.
    """
    state = current_state()
    zeilen = []
    for name, slot in state.filled_slots().items():
        value = slot.value
        if isinstance(value, list):
            text = ", ".join(str(getattr(v, "value", v)) for v in value)
        elif hasattr(value, "model_dump"):
            text = ", ".join(
                f"{k}={v}" for k, v in value.model_dump().items() if v not in (None, False)
            )
        else:
            text = str(getattr(value, "value", value))
        mark = slot.provenance.value if slot.provenance else "?"
        flag = " [zu bestätigen]" if slot.needs_confirmation else ""
        zeilen.append(f"  {name} = {text} ({mark}){flag}")

    offen = state.missing_slots()
    bereit = state.intent.is_set and (state.budget.is_set or state.use_case_tags.is_set)
    return (
        "Bekannt:\n" + ("\n".join(zeilen) if zeilen else "  nichts") + "\n"
        f"Offen: {', '.join(offen) if offen else 'nichts'}\n"
        f"Bereit für Empfehlungen: {'ja' if bereit else 'nein'}"
    )


@tool
def empfehlungen_erstellen(anzahl: int = 5) -> str:
    """Filter and score the inventory against the interview record.

    Returns the exclusion counts per constraint, then the ranked listings with their
    identifier, name, price, score and the decisive factors already worded for you.
    Quote these. Do not compute anything from them and do not add figures of your own.

    The user is shown the full result list automatically, so keep your reply short.
    """
    session_id = CURRENT_SESSION.get()
    state = current_state()

    if not state.intent.is_set:
        return (
            "Noch keine Absicht bekannt. Frage zuerst, ob gekauft oder gemietet werden "
            "soll, und trage es mit interview_merken ein."
        )

    lang = i18n.normalise(STORE.artifact(session_id, "lang") or "de")

    # A rental has to be costed over some number of days. If the user has not said,
    # the assumption is recorded in the slot rather than applied invisibly inside the
    # cost model, so the interview panel can show it as an assumption and the user can
    # correct it. DEFAULT provenance never overwrites anything they did say.
    if state.effective_intent() is Intent.MIETE and not state.mietdauer_tage.is_set:
        state.mietdauer_tage = state.mietdauer_tage.assume(
            STANDARD_MIETDAUER_TAGE,
            source="Standardannahme, keine Mietdauer genannt"
            if lang == "de"
            else "standing assumption, no rental duration stated",
        )

    result = rank(state, limit=max(1, min(anzahl, 8)), tco_fn=tco_for_state, lang=lang)

    STORE.set_artifact(session_id, "ranking", result)
    # FR-035: a recommendation must be traceable back to the scores that produced it.
    observability.record_ranking(state, result, lang)
    state.phase = state.phase.__class__.EMPFEHLUNG
    save_state(state)

    if not result.empfehlungen:
        schuld = result.report.groesster_ausschluss()
        label = constraint_label(schuld, lang) if schuld else "unbekannt"
        return (
            f"Kein Angebot erfüllt alle Kriterien. "
            f"{result.report.gesamt} geprüft, 0 übrig. "
            f"Größter Ausschlussgrund: {label} "
            f"({result.report.ausgeschlossen.get(schuld, 0)} Angebote). "
            f"Schlage vor, genau dieses Kriterium zu lockern. Erfinde kein Angebot."
        )

    zeilen = [result.report.erklaerung(lang), "", "Rangfolge:"]
    for rec in result.empfehlungen:
        preis = i18n.fmt_int(rec.listing.preis_referenz(), lang)
        einheit = "EUR/Tag" if rec.listing.listing_type == "miete" else "EUR"
        zeilen.append(
            f"{rec.rang}. {rec.listing.bezeichnung} [{rec.listing.id}] "
            f"{preis} {einheit}, {rec.score.total:.1f} Punkte"
        )
        for faktor in rec.score.top_faktoren(n=2, lang=lang):
            zeilen.append(f"     - {faktor}")
        if rec.tco_gesamt_eur:
            betrag = i18n.fmt_int(rec.tco_gesamt_eur, lang)
            if rec.listing.listing_type == "miete":
                tage = state.mietdauer_tage.value or STANDARD_MIETDAUER_TAGE
                label = (
                    f"{i18n.t('dim.mietkosten', lang)} {tage} "
                    + ("Tage" if lang == "de" else "days")
                )
            else:
                label = (
                    f"{i18n.t('dim.gesamtkosten', lang)} "
                    + ("5 Jahre" if lang == "de" else "5 years")
                )
            zeilen.append(f"     - {label}: {betrag} EUR")

    top = result.empfehlungen[0]
    if top.vergleich:
        v = top.vergleich
        zeilen.append(
            f"\nPlatz 1 gegen Platz 2: {v.punkte_vorsprung:+.1f} Punkte, "
            f"{i18n.fmt_int(v.preis_differenz_eur, lang)} EUR Preisdifferenz."
        )
    zeilen.append(
        "\nDie Liste wird der Person angezeigt. Nenne nur die ersten ein bis zwei "
        "Fahrzeuge und den wichtigsten Grund."
    )
    return "\n".join(zeilen)


AGENT_TOOLS = [interview_merken, interview_stand, empfehlungen_erstellen]
