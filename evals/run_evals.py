"""Run the persona evaluations. Bonus requirement B-2.

Two modes, and the difference is what is being measured.

    --offline   scores the deterministic pipeline against ground truth interview
                records. No model call, no API key, no network. This measures whether
                the ranking obeys hard constraints, which is a property of the engine.

    (default)   drives the real agent through each persona's turns, then scores what
                the agent actually recorded, what it recommended and what it said.
                This measures the agent.

Offline mode exists because the free tier allows 500 model requests a day and a live
run costs roughly a fifth of that. It also means the harness stays demonstrable when
the quota is gone, which on a demonstration day is not a small thing.

    python -m evals.run_evals --offline
    python -m evals.run_evals
    python -m evals.run_evals --personas umzug_miete,familie_kauf --no-judge

A live run writes evals/results.json. An offline run writes evals/results_offline.json,
so a routine offline check cannot overwrite the published live evidence. Override
either with --out.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from agent import i18n
from agent.state import (
    Budget,
    HardConstraints,
    Intent,
    InterviewState,
    Location,
    tags_from_text,
)
from agent.tools.ranking import rank
from agent.tools.tco import tco_for_state
from evals.scoring import (
    ConstraintScore,
    FaithfulnessScore,
    SlotScore,
    score_constraints,
    score_faithfulness,
    score_slots,
)

HERE = Path(__file__).resolve().parent
PERSONAS_FILE = HERE / "personas.json"
RESULTS_FILE = HERE / "results.json"
OFFLINE_RESULTS_FILE = HERE / "results_offline.json"


def load_personas() -> list[dict[str, Any]]:
    data = json.loads(PERSONAS_FILE.read_text(encoding="utf-8"))
    return data["personas"]


# ------------------------------------------------------------------ offline path


def state_from_ground_truth(persona: dict[str, Any]) -> InterviewState:
    """Build the interview record a perfect interview would have produced.

    Used only by offline mode. It is ground truth, not agent output, so scoring slot
    filling against it offline would be scoring this function against itself. Offline
    mode reports slot filling as not applicable for exactly that reason.
    """
    st = InterviewState(session_id=f"eval-{persona['id']}")
    erwartet = persona["erwartete_slots"]

    if intent := erwartet.get("intent"):
        st.intent = st.intent.state(Intent(intent))

    budget = Budget(
        max_kaufpreis_eur=erwartet.get("budget.max_kaufpreis_eur"),
        max_tagessatz_eur=erwartet.get("budget.max_tagessatz_eur"),
    )
    if budget.max_kaufpreis_eur or budget.max_tagessatz_eur:
        st.budget = st.budget.state(budget)

    constraints = HardConstraints(
        getriebe=erwartet.get("constraints_hard.getriebe"),
        kraftstoff=erwartet.get("constraints_hard.kraftstoff"),
        min_sitzplaetze=erwartet.get("constraints_hard.min_sitzplaetze"),
        min_kofferraum_liter=erwartet.get("constraints_hard.min_kofferraum_liter"),
        umweltplakette=erwartet.get("constraints_hard.umweltplakette"),
        max_kilometerstand=erwartet.get("constraints_hard.max_kilometerstand"),
        unfallfrei_erforderlich=bool(
            erwartet.get("constraints_hard.unfallfrei_erforderlich")
        ),
    )
    st.constraints_hard = st.constraints_hard.state(constraints)

    if plz := erwartet.get("location.plz"):
        st.location = st.location.state(Location(plz=plz))
    if km := erwartet.get("jahresfahrleistung_km"):
        st.jahresfahrleistung_km = st.jahresfahrleistung_km.state(km)
    if tage := erwartet.get("mietdauer_tage"):
        st.mietdauer_tage = st.mietdauer_tage.state(tage)
    if kategorien := erwartet.get("category_preference"):
        st.category_preference = st.category_preference.state(kategorien)

    text = " ".join(persona["turns"])
    st.use_case_text = st.use_case_text.state(text)
    if tags := tags_from_text(text):
        st.use_case_tags = st.use_case_tags.infer(tags)
    return st


def run_offline(persona: dict[str, Any]) -> dict[str, Any]:
    lang = i18n.normalise(persona.get("lang", "de"))
    state = state_from_ground_truth(persona)
    started = time.perf_counter()
    ranking = rank(state, limit=5, tco_fn=tco_for_state, lang=lang)
    dauer = time.perf_counter() - started

    constraints = score_constraints(
        [r.listing for r in ranking.empfehlungen], persona["harte_kriterien"]
    )
    return {
        "persona": persona["id"],
        "modus": "offline",
        "lang": lang,
        "slots": None,
        "constraints": constraints.model_dump(),
        "faithfulness": None,
        "zuege": 0,
        "modellaufrufe": 0,
        "sekunden": round(dauer, 3),
        "empfehlungen": [r.listing.id for r in ranking.empfehlungen],
        "antwort": "",
    }


# ------------------------------------------------------------------ live path


def run_live(persona: dict[str, Any], mit_richter: bool = True) -> dict[str, Any]:
    """Drive the real agent through the persona's turns, then score what it did."""
    from agent.session import ranking_for, run_turn, state_for
    from agent.store import STORE

    lang = i18n.normalise(persona.get("lang", "de"))
    session_id = f"eval-{persona['id']}-{int(time.time())}"

    antworten: list[str] = []
    aufrufe = 0
    gedrosselt = False
    started = time.perf_counter()

    for nachricht in persona["turns"]:
        result = run_turn(session_id, nachricht, lang)
        antworten.append(result.antwort)
        aufrufe += result.modellaufrufe
        if result.gedrosselt:
            gedrosselt = True
            break

    # One explicit request for recommendations, so every persona reaches the ranking
    # even when the agent would have asked another question first. Without it the
    # constraint measure would only ever score the talkative personas.
    if not gedrosselt:
        bitte = (
            "Bitte zeig mir jetzt die Empfehlungen."
            if lang == "de"
            else "Please show me the recommendations now."
        )
        result = run_turn(session_id, bitte, lang)
        antworten.append(result.antwort)
        aufrufe += result.modellaufrufe
        gedrosselt = result.gedrosselt

    dauer = time.perf_counter() - started
    state = state_for(session_id)
    ranking = ranking_for(session_id)

    slots = score_slots(state, persona["erwartete_slots"])
    constraints = score_constraints(
        [r.listing for r in ranking.empfehlungen] if ranking else [],
        persona["harte_kriterien"],
    )

    letzte = next((a for a in reversed(antworten) if a.strip()), "")
    faith = score_faithfulness(letzte, ranking, state)
    if mit_richter and not gedrosselt:
        from evals.judge import judge_faithfulness

        punkte, begruendung = judge_faithfulness(letzte, ranking, persona["turns"])
        faith.richter_punktzahl = punkte
        faith.richter_begruendung = begruendung

    # Each persona is an independent conversation. Leaving the record behind would let
    # one persona's interview leak into the next run's session lookup.
    STORE.clear(session_id)

    return {
        "persona": persona["id"],
        "modus": "live",
        "lang": lang,
        "slots": slots.model_dump() | {"anteil": round(slots.anteil, 3)},
        "constraints": constraints.model_dump(),
        "faithfulness": faith.model_dump()
        | {"zahlen_anteil": round(faith.zahlen_anteil, 3)},
        "zuege": len(antworten),
        "modellaufrufe": aufrufe,
        "sekunden": round(dauer, 1),
        "gedrosselt": gedrosselt,
        "empfehlungen": [r.listing.id for r in ranking.empfehlungen] if ranking else [],
        "antwort": letzte[:600],
    }


# ------------------------------------------------------------------ reporting


def _cell(value: Optional[float], breite: int = 6) -> str:
    return "n/a".rjust(breite) if value is None else f"{value:.2f}".rjust(breite)


def print_table(results: list[dict[str, Any]]) -> None:
    print()
    print(f"{'persona':<20}{'slots':>7}{'viol':>6}{'nums':>7}{'judge':>7}{'turns':>7}{'calls':>7}")
    print("-" * 61)
    for r in results:
        slots = r["slots"]["anteil"] if r["slots"] else None
        nums = r["faithfulness"]["zahlen_anteil"] if r["faithfulness"] else None
        judge = (r["faithfulness"] or {}).get("richter_punktzahl")
        verstoesse = r["constraints"]["verstoesse"]
        print(
            f"{r['persona']:<20}{_cell(slots, 7)}{verstoesse:>6}"
            f"{_cell(nums, 7)}{_cell(judge, 7)}{r['zuege']:>7}{r['modellaufrufe']:>7}"
        )
    print("-" * 61)

    verstoesse = sum(r["constraints"]["verstoesse"] for r in results)
    slot_werte = [r["slots"]["anteil"] for r in results if r["slots"]]
    zahl_werte = [r["faithfulness"]["zahlen_anteil"] for r in results if r["faithfulness"]]
    richter = [
        r["faithfulness"]["richter_punktzahl"]
        for r in results
        if r["faithfulness"] and r["faithfulness"].get("richter_punktzahl") is not None
    ]

    def mittel(xs: list[float]) -> str:
        return f"{sum(xs) / len(xs):.2f}" if xs else "n/a"

    print(f"  hard constraint violations, all personas : {verstoesse}")
    print(f"  slot filling, mean                       : {mittel(slot_werte)}")
    print(f"  figures traceable to data, mean          : {mittel(zahl_werte)}")
    print(f"  judged faithfulness, mean                : {mittel(richter)}")
    print(f"  model calls, total                       : {sum(r['modellaufrufe'] for r in results)}")

    leer = [r for r in results if r["constraints"].get("erwartet_leer")]
    for r in leer:
        korrekt = r["constraints"].get("leer_korrekt")
        print(
            f"  {r['persona']}: expected no survivors, "
            f"{'refused correctly' if korrekt else 'RETURNED RESULTS ANYWAY'}"
        )

    for r in results:
        details = r["constraints"]["details"]
        if details:
            print(f"\n  {r['persona']} violations:")
            for d in details:
                print(f"    {d}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline", action="store_true",
        help="score the deterministic pipeline only. No model, no key, no network.",
    )
    parser.add_argument("--personas", default="", help="comma separated ids to run")
    parser.add_argument("--no-judge", action="store_true", help="skip the LLM judge")
    parser.add_argument(
        "--out",
        default="",
        help="where to write results. Defaults to results.json for a live run and "
        "results_offline.json otherwise.",
    )
    args = parser.parse_args()

    # Offline mode writes somewhere else by default. The two runs do not measure the
    # same thing: offline scores only the deterministic pipeline and leaves slot
    # filling, traceability and the judge null. Letting it default to the same path
    # meant a routine offline check silently overwrote the published live results with
    # a file whose interesting columns are all empty, which is exactly how this
    # project once ended up shipping an eval table its own evidence did not support.
    ziel = args.out or str(
        OFFLINE_RESULTS_FILE if args.offline else RESULTS_FILE
    )

    personas = load_personas()
    if args.personas:
        wanted = {p.strip() for p in args.personas.split(",") if p.strip()}
        unknown = wanted - {p["id"] for p in personas}
        if unknown:
            print(f"unknown personas: {', '.join(sorted(unknown))}", file=sys.stderr)
            return 2
        personas = [p for p in personas if p["id"] in wanted]

    modus = "offline" if args.offline else "live"
    print(f"fahrbereit persona evaluations, {modus} mode, {len(personas)} personas")
    if not args.offline:
        # The same loader the backend uses. Nothing here reads .env in offline mode,
        # which is what lets that mode run with no key at all.
        from run_backend import load_env

        load_env()
        print("this calls the real agent and spends model quota")

    results = []
    for persona in personas:
        print(f"  {persona['id']} ...", end=" ", flush=True)
        try:
            result = (
                run_offline(persona)
                if args.offline
                else run_live(persona, mit_richter=not args.no_judge)
            )
        except Exception as exc:  # noqa: BLE001 - one persona must not kill the run
            print(f"FAILED: {type(exc).__name__}: {exc}")
            results.append(
                {
                    "persona": persona["id"], "modus": modus, "lang": persona.get("lang"),
                    "fehler": f"{type(exc).__name__}: {exc}", "slots": None,
                    "constraints": {"geprueft": 0, "verstoesse": 0, "details": []},
                    "faithfulness": None, "zuege": 0, "modellaufrufe": 0,
                    "empfehlungen": [], "antwort": "",
                }
            )
            continue
        print(f"{result['constraints']['verstoesse']} violations, {result['modellaufrufe']} calls")
        results.append(result)

    print_table(results)

    payload = {
        "erzeugt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modus": modus,
        "personas": len(results),
        "ergebnisse": results,
    }
    Path(ziel).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\nwritten to {ziel}")

    return 1 if any(r["constraints"]["verstoesse"] for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
