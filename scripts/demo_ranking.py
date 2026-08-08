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
            unfallfrei_erforderlich=True, umweltplakette="gruen",
        )
    )
    st.location = st.location.state(Location(plz="80339", ort="Muenchen"))
    return "Familie, zwei Kinder, Muenchen", st


def persona_pendler() -> tuple[str, InterviewState]:
    text = "Ich pendle jeden Tag 45 km in die Stadt zur Arbeit. Automatik bitte."
    st = InterviewState(session_id="demo-pendler")
    st.intent = st.intent.state(Intent.KAUF)
    st.use_case_text = st.use_case_text.state(text)
    st.use_case_tags = st.use_case_tags.infer(tags_from_text(text), confidence=0.85)
    st.budget = st.budget.state(Budget(max_kaufpreis_eur=32_000))
    st.jahresfahrleistung_km = st.jahresfahrleistung_km.state(22_000)
    st.constraints_hard = st.constraints_hard.state(
        HardConstraints(getriebe="Automatik", umweltplakette="gruen", unfallfrei_erforderlich=True)
    )
    st.location = st.location.state(Location(plz="10115", ort="Berlin", max_entfernung_km=300))
    return "Pendler, 22.000 km im Jahr, Berlin", st


def persona_umzug() -> tuple[str, InterviewState]:
    text = "Ich brauche fuer ein Wochenende ein Auto fuer einen Umzug."
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
    print("INTERVIEW")
    print(RULE)
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
        flag = " (zu bestaetigen)" if slot.needs_confirmation else ""
        print(f"  {name:<24} {str(value)[:44]:<44} [{mark}]{flag}")
    missing = state.missing_slots()
    if missing:
        print(f"\n  offen: {', '.join(missing)}")
    print()


def print_filter(result) -> None:
    print("HARTE FILTER")
    print(RULE)
    print(f"  {result.report.gesamt} Angebote geprueft")
    for key, count in result.report.ausgeschlossen.items():
        print(f"    minus {count:>4}  {CONSTRAINT_LABELS.get(key, key)}")
    print(f"  {result.report.uebrig} verblieben\n")


def print_weights(result) -> None:
    print("GEWICHTUNG aus dem Interview")
    print(RULE)
    for name, weight in sorted(result.gewichte.items(), key=lambda kv: -kv[1]):
        print(f"  {name:<22} {weight:>6.1%}  {bar(weight * 100 / max(result.gewichte.values()))}")
    print()


def print_ranking(result, state: InterviewState) -> None:
    print("RANGLISTE")
    print(RULE)
    unit = "EUR/Tag" if state.effective_intent() is Intent.MIETE else "EUR"
    print(f"  {'#':<3}{'Fahrzeug':<40}{'Punkte':>8}{'Preis':>12} {unit}")
    for rec in result.empfehlungen:
        print(
            f"  {rec.rang:<3}{rec.listing.bezeichnung[:38]:<40}"
            f"{rec.score.total:>8.1f}{euro(rec.listing.preis_referenz()):>12}"
        )
    print()


def print_winner(result, state: InterviewState) -> None:
    top = result.empfehlungen[0]
    listing = top.listing
    print("WARUM DIESES AUTO")
    print(RULE)
    print(f"  {listing.bezeichnung}   [{listing.id}]")
    print(
        f"  {listing.category}, EZ {listing.erstzulassung}, "
        f"{euro(listing.kilometerstand)} km, {listing.leistung_kw} kW / "
        f"{listing.leistung_ps} PS, {listing.getriebe}, {listing.kraftstoff}"
    )
    print(f"  {listing.haendler}, {listing.standort_plz} {listing.standort_ort}\n")

    print(f"  {'Dimension':<24}{'Gewicht':>8}{'Wert':>7}{'Beitrag':>9}  Begruendung")
    for dim in top.score.dimensionen:
        print(
            f"  {dim.label:<24}{dim.gewicht:>8.2f}{dim.rohwert:>7.1f}{dim.beitrag:>9.2f}"
            f"  {dim.begruendung[:34]}"
        )
    total = sum(d.beitrag for d in top.score.dimensionen)
    print(f"  {'GESAMT':<24}{'':>8}{'':>7}{total:>9.2f}")
    print(f"  Summe der Beitraege {total:.2f} entspricht dem Gesamtwert "
          f"{top.score.total:.2f}\n")

    print("  Ausschlaggebend:")
    for factor in top.score.top_faktoren():
        print(f"    - {factor}")
    print()


def print_tco(result, state: InterviewState) -> None:
    top = result.empfehlungen[0]
    km = state.jahresfahrleistung_km.value or 15_000
    tco = cost_of_ownership(top.listing, km)
    print(f"GESAMTKOSTEN ueber fuenf Jahre bei {euro(km)} km im Jahr")
    print(RULE)
    for label, value in tco.posten():
        print(f"  {label:<24}{euro(value):>12} EUR")
    print(f"  {'-' * 36}")
    print(f"  {'GESAMT':<24}{euro(tco.gesamt_5j_eur):>12} EUR")
    if top.listing.preis_eur:
        print(f"  {'davon Restwert':<24}{euro(tco.restwert_eur):>12} EUR")
    print(f"\n  Kfz-Steuer: {tco.steuer_hinweis}")
    print(f"  {tco.schaetzung_hinweis}\n")


def print_comparison(result) -> None:
    top = result.empfehlungen[0]
    if not top.vergleich:
        return
    v = top.vergleich
    print("GEGEN DEN ZWEITPLATZIERTEN")
    print(RULE)
    print(f"  Platz 2: {v.gegen_bezeichnung} [{v.gegen_id}]")
    print(f"  Vorsprung        {v.punkte_vorsprung:>10.2f} Punkte")
    print(f"  Preisdifferenz   {euro(v.preis_differenz_eur):>10} EUR")
    print(f"  Laufleistung     {euro(v.km_differenz):>10} km")
    print(f"  Alter            {v.alter_differenz_jahre:>10.1f} Jahre")
    if v.kosten_differenz_eur is not None:
        print(f"  Gesamtkosten     {euro(v.kosten_differenz_eur):>10} EUR ueber fuenf Jahre")
    print()


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
                print(f"unknown dimension {key!r}. known: {', '.join(d.value for d in Dimension)}")
                return 2
            overrides[key] = float(value)
        state.preferences_soft = state.preferences_soft.state(overrides)

    print()
    print("=" * 78)
    print(f"  fahrbereit, Rangfolge-Engine   [{title}]")
    print("=" * 78)
    print(f'  "{state.use_case_text.value}"\n')

    print_interview(state)

    result = rank(state, limit=args.limit, tco_fn=tco_for_state)

    print_filter(result)
    if not result.empfehlungen:
        worst = result.report.groesster_ausschluss()
        print("Keine Treffer. Kein Angebot erfuellt alle harten Kriterien.")
        if worst:
            print(f"Groesster Ausschlussgrund: {CONSTRAINT_LABELS.get(worst, worst)}.")
        return 1

    print_weights(result)
    print_ranking(result, state)
    print_winner(result, state)
    print_tco(result, state)
    print_comparison(result)

    print(RULE)
    print("  Alle Zahlen deterministisch berechnet. Kein Modellaufruf, kein Netzwerk.")
    print(RULE)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
