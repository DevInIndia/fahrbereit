"""The faithfulness judge. Runs on the cheap model, so it costs nothing scarce.

Gemma has 14,400 requests a day against the reasoning model's 500, and it is sixteen
times slower, which is why docs/spike-notes.md put it off every interactive path. An
offline eval is exactly the work it is good for: nobody is waiting, and the volume is
the part that matters.

The judge is asked one narrow question. It is given the agent's reply and the figures
the agent was actually handed, and asked whether the reply's claims are supported by
those figures. It is not asked whether the recommendation is good, whether the ranking
is sensible, or anything else it would be happy to answer and unqualified to. Scoring
a recommendation's quality by model judgement would be marking our own homework with a
marker that cannot check arithmetic.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from agent.model import CallType, get_model

log = logging.getLogger("fahrbereit.evals.judge")

PROMPT = """You are checking one thing only: whether a car advisor's reply is
faithful to the data it was given. You are not judging whether the recommendation is
good, or whether the ranking is sensible. Only faithfulness.

WHAT THE CUSTOMER SAID
{gespraech}

Anything the customer said is established fact. The advisor referring back to the
customer's own stated situation is faithful, not invented.

THE DATA THE ADVISOR WAS GIVEN
{daten}

THE ADVISOR'S REPLY
{antwort}

Answer these, and nothing else:
1. Does every factual claim in the reply follow from the data above?
2. Does the reply state any figure, vehicle, or property that is absent from the data?
3. Does the reply describe a car as satisfying a requirement the data shows it does
   not satisfy?

Reply with a single JSON object and no other text:
{{"punktzahl": <0.0 to 1.0>, "begruendung": "<one sentence>", "erfundenes": ["<claim>", ...]}}

punktzahl 1.0 means every claim traces to the data. 0.0 means the reply is largely
invented. Unsupported claims lower the score in proportion to how much of the reply
rests on them."""

JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def _daten_fuer_richter(ranking, limit: int = 3) -> str:
    """The figures the agent was handed, in the same shape the judge is asked about."""
    if ranking is None:
        return "No ranking was produced. The advisor had no vehicle data to work from."

    zeilen = [
        f"Listings checked: {ranking.report.gesamt}",
        f"Listings remaining after the filter: {ranking.report.uebrig}",
        f"Excluded per constraint: {dict(ranking.report.ausgeschlossen)}",
    ]
    if ranking.report.angenommener_radius_km:
        zeilen.append(f"Assumed pickup radius: {ranking.report.angenommener_radius_km} km")

    for rec in ranking.empfehlungen[:limit]:
        listing = rec.listing
        preis = (
            f"{listing.preis_eur} EUR"
            if listing.listing_type == "kauf"
            else f"{listing.tagessatz_eur} EUR per day"
        )
        zeilen.append(
            f"\nRank {rec.rang}: {listing.bezeichnung} [{listing.id}]\n"
            f"  type={listing.listing_type} price={preis} "
            f"first_registered={listing.erstzulassung} mileage={listing.kilometerstand} km\n"
            f"  power={listing.leistung_kw} kW fuel={listing.kraftstoff} "
            f"transmission={listing.getriebe} seats={listing.sitzplaetze} "
            f"boot={listing.kofferraum_liter} l\n"
            f"  accident_free={listing.unfallfrei} badge={listing.umweltplakette} "
            f"location={listing.standort_plz} {listing.standort_ort}\n"
            f"  score={rec.score.total} cost_figure={rec.tco_gesamt_eur} EUR\n"
            f"  decisive: {'; '.join(rec.score.top_faktoren(n=3))}"
        )
    return "\n".join(zeilen)


def judge_faithfulness(
    antwort: str, ranking, gespraech: Optional[list[str]] = None
) -> tuple[Optional[float], str]:
    """Score one reply for faithfulness. Returns (score, reason).

    `gespraech` is what the customer actually said. Without it the judge marks the
    advisor down for referring to the customer's own stated situation, which is the
    one thing it can always safely refer to.

    A judge that fails is reported as unavailable rather than as a zero. Scoring an
    infrastructure failure as a model failure would quietly corrupt the results table,
    which is the same class of error as a silent fallback.
    """
    if not (antwort or "").strip():
        return 0.0, "the advisor said nothing"

    prompt = PROMPT.format(
        gespraech="\n".join(f"- {t}" for t in (gespraech or [])) or "(not recorded)",
        daten=_daten_fuer_richter(ranking),
        antwort=antwort.strip(),
    )
    try:
        model = get_model(CallType.CHEAP)
        raw = model.invoke(prompt)
        text = raw.content if isinstance(raw.content, str) else " ".join(
            block.get("text", "") for block in raw.content if isinstance(block, dict)
        )
    except Exception as exc:  # noqa: BLE001 - reported, never silently scored
        log.warning("judge unavailable: %s", exc)
        return None, f"judge unavailable: {type(exc).__name__}"

    match = JSON_BLOCK.search(text or "")
    if not match:
        return None, "judge returned no parseable JSON"
    try:
        parsed = json.loads(match.group())
    except json.JSONDecodeError:
        return None, "judge returned malformed JSON"

    try:
        score = float(parsed.get("punktzahl"))
    except (TypeError, ValueError):
        return None, "judge returned no numeric score"

    begruendung = str(parsed.get("begruendung", "")).strip()
    erfundenes = parsed.get("erfundenes") or []
    if erfundenes:
        begruendung += f" Unsupported: {'; '.join(str(x) for x in erfundenes[:3])}"
    return max(0.0, min(1.0, score)), begruendung
