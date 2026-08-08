"""See the ranking engine work, before any interface exists.

Runs a fixed persona through the whole deterministic pipeline and prints the result:
the hard filter with its per constraint drop counts, the weights derived from the
interview, the ranked cars, the score breakdown for the winner, its five year cost of
ownership, and why it beat the runner up.

No model is called. No network is touched. Every number printed is computed here.

Run:  python -m scripts.demo_ranking
      python -m scripts.demo_ranking --persona familie
      python -m scripts.demo_ranking --persona pendler --weights gesamtkosten=1.0
"""

from __future__ import annotations

import argparse
import sys

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
from agent.tools.ranking import CONSTRAINT_LABELS, rank
from agent.tools.tco import cost_of_ownership, tco_for_state

RULE = "-" * 78

# Terminal fallback only. Proper umlauts live in the data and in every user facing
# string; this maps them down solely when the console encoding cannot render them,
# which on Windows means a cp1252 or cp437 code page. Nothing outside this print
# layer ever sees a transliterated form, and the web interface never uses it.
_FALLBACK = str.maketrans(
    {"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"}
)


def _console_supports_utf8() -> bool:
    encoding = (getattr(sys.stdout, "encoding", None) or "").lower()
    return "utf" in encoding


def say(text: str = "") -> None:
    """Print, degrading to transliteration only if the console cannot cope."""
    if not _console_supports_utf8():
        text = text.translate(_FALLBACK)
    print(text)


def euro(value: int | float | None) -> str:
    if value is None:
        return "n/a"
    return f"{int(value):,}".replace(",", ".")


def bar(value: float, width: int = 22) -> str:
    filled = int(round(value / 100 * width))
    return "#" * filled + "." * (width - filled)


# ---------------------------------------------------------------- personas


def persona_familie() -> tuple[str, InterviewState]:
    text = (
        "Ich fahre meine zwei Kinder zur Schule und einmal im Monat 300 km zu meinen "
        "Eltern. Budget etwa 25.000 Euro."
    )
    st = InterviewState(session_id="demo-familie")
    st.intent = st.intent.state(Intent.KAUF, source="sagt kaufen")
    st.use_case_text = st.use_case_text.state(text)
    st.use_case_tags = st.use_case_tags.infer(
        tags_from_text(text) + [UseCaseTag.LANGSTRECKE], confidence=0.8,
        source="abgeleitet aus der Beschreibung",
    )
    st.budget = st.budget.state(Budget(max_kaufpreis_eur=25_000))
    st.jahresfahrleistung_km = st.jahresfahrleistung_km.infer(
        15_000, confidence=0.6, source="Schulweg plus monatliche Langstrecke"
    )
    st.constraints_hard = st.constraints_hard.state(
        HardConstraints(
            min_sitzplaetze=5, min_kofferraum_liter=400,
            unfallfrei_erforderlich=True, umweltplakette="grün",
        )
    )
    st.location = st.location.state(Location(plz="80339", ort="München"))
    return "Familie, zwei Kinder, München", st


def persona_pendler() -> tuple[str, InterviewState]:
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
    return "Pendler, 22.000 km im Jahr, Berlin", st


def persona_umzug() -> tuple[str, InterviewState]:
    text = "Ich brauche für ein Wochenende ein Auto für einen Umzug."
    st = InterviewState(session_id="demo-umzug")
    st.intent = st.intent.state(Intent.MIETE)
    st.use_case_text = st.use_case_text.state(text)
    st.use_case_tags = st.use_case_tags.infer(tags_from_text(text), confidence=0.9)
    st.budget = st.budget.state(Budget(max_tagessatz_eur=95))
    st.jahresfahrleistung_km = st.jahresfahrleistung_km.infer(
        5_000, confidence=0.5, source="einmalige Wochenendmiete"
    )
    st.constraints_hard = st.constraints_hard.state(HardConstraints(min_kofferraum_liter=550))
    st.location = st.location.state(Location(plz="20095", ort="Hamburg"))
    return "Umzug am Wochenende, Miete, Hamburg", st


PERSONAS = {
    "familie": persona_familie,
    "pendler": persona_pendler,
    "umzug": persona_umzug,
}


# ---------------------------------------------------------------- output


def print_interview(state: InterviewState) -> None:
    say("INTERVIEW")
    say(RULE)
    for name, slot in state.filled_slots().items():
        mark = {"stated": "gesagt", "inferred": "abgeleitet", "default": "Standard"}[
            slot.provenance.value
        ]
        value = slot.value
        if isinstance(value, list):
            value = ", ".join(str(v.value if hasattr(v, "value") else v) for v in value)
        elif hasattr(value, "model_dump"):
            value = ", ".join(
                f"{k}={v}" for k, v in value.model_dump().items() if v not in (None, False)
            )
        elif hasattr(value, "value"):
            value = value.value
        flag = " (zu bestätigen)" if slot.needs_confirmation else ""
        say(f"  {name:<24} {str(value)[:44]:<44} [{mark}]{flag}")
    missing = state.missing_slots()
    if missing:
        say(f"\n  offen: {', '.join(missing)}")
    say()


def print_filter(result) -> None:
    say("HARTE FILTER")
    say(RULE)
    say(f"  {result.report.gesamt} Angebote geprüft")
    for key, count in result.report.ausgeschlossen.items():
        say(f"    minus {count:>4}  {CONSTRAINT_LABELS.get(key, key)}")
    say(f"  {result.report.uebrig} verblieben\n")


def print_weights(result) -> None:
    say("GEWICHTUNG aus dem Interview")
    say(RULE)
    for name, weight in sorted(result.gewichte.items(), key=lambda kv: -kv[1]):
        say(f"  {name:<22} {weight:>6.1%}  {bar(weight * 100 / max(result.gewichte.values()))}")
    say()


def print_ranking(result, state: InterviewState) -> None:
    say("RANGLISTE")
    say(RULE)
    unit = "EUR/Tag" if state.effective_intent() is Intent.MIETE else "EUR"
    say(f"  {'#':<3}{'Fahrzeug':<40}{'Punkte':>8}{'Preis':>12} {unit}")
    for rec in result.empfehlungen:
        say(
            f"  {rec.rang:<3}{rec.listing.bezeichnung[:38]:<40}"
            f"{rec.score.total:>8.1f}{euro(rec.listing.preis_referenz()):>12}"
        )
    say()


def print_winner(result, state: InterviewState) -> None:
    top = result.empfehlungen[0]
    listing = top.listing
    say("WARUM DIESES AUTO")
    say(RULE)
    say(f"  {listing.bezeichnung}   [{listing.id}]")
    say(
        f"  {listing.category}, EZ {listing.erstzulassung}, "
        f"{euro(listing.kilometerstand)} km, {listing.leistung_kw} kW / "
        f"{listing.leistung_ps} PS, {listing.getriebe}, {listing.kraftstoff}"
    )
    say(f"  {listing.haendler}, {listing.standort_plz} {listing.standort_ort}\n")

    say(f"  {'Dimension':<24}{'Gewicht':>8}{'Wert':>7}{'Beitrag':>9}  Begründung")
    for dim in top.score.dimensionen:
        say(
            f"  {dim.label:<24}{dim.gewicht:>8.2f}{dim.rohwert:>7.1f}{dim.beitrag:>9.2f}"
            f"  {dim.begruendung[:34]}"
        )
    total = sum(d.beitrag for d in top.score.dimensionen)
    say(f"  {'GESAMT':<24}{'':>8}{'':>7}{total:>9.2f}")
    say(f"  Summe der Beiträge {total:.2f} entspricht dem Gesamtwert "
          f"{top.score.total:.2f}\n")

    say("  Ausschlaggebend:")
    for factor in top.score.top_faktoren():
        say(f"    - {factor}")
    say()


def print_tco(result, state: InterviewState) -> None:
    top = result.empfehlungen[0]
    km = state.jahresfahrleistung_km.value or 15_000
    tco = cost_of_ownership(top.listing, km)
    say(f"GESAMTKOSTEN über fünf Jahre bei {euro(km)} km im Jahr")
    say(RULE)
    for label, value in tco.posten():
        say(f"  {label:<24}{euro(value):>12} EUR")
    say(f"  {'-' * 36}")
    say(f"  {'GESAMT':<24}{euro(tco.gesamt_5j_eur):>12} EUR")
    if top.listing.preis_eur:
        say(f"  {'davon Restwert':<24}{euro(tco.restwert_eur):>12} EUR")
    say(f"\n  Kfz-Steuer: {tco.steuer_hinweis}")
    say(f"  {tco.schaetzung_hinweis}\n")


def print_comparison(result) -> None:
    top = result.empfehlungen[0]
    if not top.vergleich:
        return
    v = top.vergleich
    say("GEGEN DEN ZWEITPLATZIERTEN")
    say(RULE)
    say(f"  Platz 2: {v.gegen_bezeichnung} [{v.gegen_id}]")
    say(f"  Vorsprung        {v.punkte_vorsprung:>10.2f} Punkte")
    say(f"  Preisdifferenz   {euro(v.preis_differenz_eur):>10} EUR")
    say(f"  Laufleistung     {euro(v.km_differenz):>10} km")
    say(f"  Alter            {v.alter_differenz_jahre:>10.1f} Jahre")
    if v.kosten_differenz_eur is not None:
        say(f"  Gesamtkosten     {euro(v.kosten_differenz_eur):>10} EUR über fünf Jahre")
    say()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--persona", choices=sorted(PERSONAS), default="familie")
    parser.add_argument("--limit", type=int, default=6)
    parser.add_argument(
        "--weights",
        default=None,
        help="Override weights, for example gesamtkosten=1.0 or preis_spielraum=0.7,zustand=0.3",
    )
    args = parser.parse_args()

    title, state = PERSONAS[args.persona]()

    if args.weights:
        overrides: dict[str, float] = {}
        for pair in args.weights.split(","):
            key, _, value = pair.partition("=")
            key = key.strip()
            if key not in {d.value for d in Dimension}:
                say(f"unknown dimension {key!r}. known: {', '.join(d.value for d in Dimension)}")
                return 2
            overrides[key] = float(value)
        state.preferences_soft = state.preferences_soft.state(overrides)

    say()
    say("=" * 78)
    say(f"  fahrbereit, Rangfolge-Engine   [{title}]")
    say("=" * 78)
    say(f'  "{state.use_case_text.value}"\n')

    print_interview(state)

    result = rank(state, limit=args.limit, tco_fn=tco_for_state)

    print_filter(result)
    if not result.empfehlungen:
        worst = result.report.groesster_ausschluss()
        say("Keine Treffer. Kein Angebot erfuellt alle harten Kriterien.")
        if worst:
            say(f"Größter Ausschlussgrund: {CONSTRAINT_LABELS.get(worst, worst)}.")
        return 1

    print_weights(result)
    print_ranking(result, state)
    print_winner(result, state)
    print_tco(result, state)
    print_comparison(result)

    say(RULE)
    say("  Alle Zahlen deterministisch berechnet. Kein Modellaufruf, kein Netzwerk.")
    say(RULE)
    say()
    return 0


if __name__ == "__main__":
    sys.exit(main())
