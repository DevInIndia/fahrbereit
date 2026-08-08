"""Two stage ranking: a boolean hard filter, then a transparent weighted score.

The model never touches either stage. It reads the output and narrates it. Every
number a user sees originates here, which is what makes a recommendation auditable
and reproducible rather than a matter of opinion.

PROVENANCE. Every numeric constant in this module is INVENTED. Not one weight,
divisor or curve parameter is traceable to a published reference, a market study or
fitted data. They were chosen so that the scoring behaves sensibly and the ordering
is defensible when read aloud.

That is a weaker claim than the module's transparency might suggest, and it is stated
here rather than left to be discovered. What the ranking genuinely guarantees is that
it is deterministic, that the arithmetic is checkable, that every score decomposes
into named contributions, and that a user can change the weights and watch the effect.
What it does not guarantee is that these particular weights are the correct ones for
any real buyer. The weights being user adjustable is the honest answer to that: the
defaults are a starting position, not a finding.

The full audit, including which constants would not survive a judge asking where they
came from, is in specs/001-fahrbereit-agent/research.md.
"""

from __future__ import annotations

from typing import Callable, Iterable, Optional, Sequence

from pydantic import BaseModel, Field

from agent.listing import PLAKETTEN_RANG, Listing, load_listings
from agent.state import Dimension, Intent, InterviewState
from agent.tools.geo import distance_km

# Constraint identities, in the order they are applied. A listing is attributed to
# the first constraint it fails, so the counts sum to the number excluded and the
# report can be read aloud without double counting.
CONSTRAINT_ORDER: tuple[str, ...] = (
    "angebotsart",
    "kategorie",
    "budget",
    "getriebe",
    "kraftstoff",
    "sitzplaetze",
    "kofferraum",
    "umweltplakette",
    "kilometerstand",
    "unfallfrei",
    "entfernung",
)

# Human readable, for the progress surface. The user sees these, not the keys.
CONSTRAINT_LABELS: dict[str, str] = {
    "angebotsart": "Angebotsart",
    "kategorie": "Fahrzeugkategorie",
    "budget": "Budget",
    "getriebe": "Getriebe",
    "kraftstoff": "Kraftstoff",
    "sitzplaetze": "Sitzplätze",
    "kofferraum": "Kofferraumvolumen",
    "umweltplakette": "Umweltplakette",
    "kilometerstand": "Kilometerstand",
    "unfallfrei": "Unfallfreiheit",
    "entfernung": "Entfernung",
}

DIMENSION_LABELS: dict[Dimension, str] = {
    Dimension.PREIS_SPIELRAUM: "Preisspielraum",
    Dimension.GESAMTKOSTEN: "Gesamtkosten",
    Dimension.ALTER_LAUFLEISTUNG: "Alter und Laufleistung",
    Dimension.EINSATZZWECK: "Einsatzzweck",
    Dimension.ZUSTAND: "Zustand",
    Dimension.ENTFERNUNG: "Entfernung",
}


class FilterReport(BaseModel):
    """What the hard filter did, in terms the user can be told."""

    gesamt: int
    uebrig: int
    ausgeschlossen: dict[str, int] = Field(default_factory=dict)

    @property
    def ausgeschlossen_gesamt(self) -> int:
        return sum(self.ausgeschlossen.values())

    def erklaerung(self) -> str:
        if not self.ausgeschlossen:
            return f"{self.gesamt} Angebote geprüft, keines ausgeschlossen."
        parts = [
            f"{CONSTRAINT_LABELS.get(k, k)} {v}"
            for k, v in sorted(self.ausgeschlossen.items(), key=lambda kv: -kv[1])
        ]
        return (
            f"{self.gesamt} Angebote geprüft, {self.ausgeschlossen_gesamt} ausgeschlossen "
            f"({', '.join(parts)}), {self.uebrig} verblieben."
        )

    def groesster_ausschluss(self) -> Optional[str]:
        """The constraint to suggest relaxing when nothing survives."""
        if not self.ausgeschlossen:
            return None
        return max(self.ausgeschlossen.items(), key=lambda kv: kv[1])[0]


class DimensionScore(BaseModel):
    name: Dimension
    label: str
    gewicht: float
    rohwert: float   # 0 to 100 on the dimension's own scale
    beitrag: float   # gewicht * rohwert
    begruendung: str


class ScoreBreakdown(BaseModel):
    dimensionen: list[DimensionScore]
    total: float

    def top_faktoren(self, n: int = 3) -> list[str]:
        ranked = sorted(self.dimensionen, key=lambda d: -d.beitrag)
        return [d.begruendung for d in ranked[:n] if d.beitrag > 0]


class Comparison(BaseModel):
    """Quantified deltas only, so narration has facts and cannot invent any."""

    gegen_id: str
    gegen_bezeichnung: str
    punkte_vorsprung: float
    preis_differenz_eur: Optional[int] = None
    km_differenz: Optional[int] = None
    alter_differenz_jahre: Optional[float] = None
    kosten_differenz_eur: Optional[int] = None


class Recommendation(BaseModel):
    listing: Listing
    score: ScoreBreakdown
    rang: int
    tco_gesamt_eur: Optional[int] = None
    vergleich: Optional[Comparison] = None


class RankingResult(BaseModel):
    report: FilterReport
    empfehlungen: list[Recommendation]
    gewichte: dict[str, float]


# ---------------------------------------------------------------- stage 1


def _fails(listing: Listing, state: InterviewState) -> Optional[str]:
    """The first constraint this listing fails, or None if it survives.

    Order matters and is fixed by CONSTRAINT_ORDER, because attributing every
    exclusion to exactly one constraint is what makes the counts add up.
    """
    intent = state.effective_intent()
    constraints = state.constraints_hard.value
    budget = state.budget.value
    location = state.location.value

    if intent is not Intent.UNENTSCHIEDEN and listing.listing_type != intent.value:
        return "angebotsart"

    if state.category_preference.value and listing.category not in state.category_preference.value:
        return "kategorie"

    if budget:
        ceiling = budget.ceiling_for(intent)
        if ceiling is not None and listing.preis_referenz() > ceiling:
            return "budget"

    if constraints:
        if constraints.getriebe and listing.getriebe != constraints.getriebe:
            return "getriebe"
        if constraints.kraftstoff and listing.kraftstoff not in constraints.kraftstoff:
            return "kraftstoff"
        if constraints.min_sitzplaetze and listing.sitzplaetze < constraints.min_sitzplaetze:
            return "sitzplaetze"
        if (
            constraints.min_kofferraum_liter
            and listing.kofferraum_liter < constraints.min_kofferraum_liter
        ):
            return "kofferraum"
        if constraints.umweltplakette:
            required = PLAKETTEN_RANG.get(constraints.umweltplakette, 0)
            if PLAKETTEN_RANG.get(listing.umweltplakette, 0) < required:
                return "umweltplakette"
        if (
            constraints.max_kilometerstand
            and listing.kilometerstand > constraints.max_kilometerstand
        ):
            return "kilometerstand"
        if constraints.unfallfrei_erforderlich and not listing.unfallfrei:
            return "unfallfrei"

    max_km = (constraints.max_entfernung_km if constraints else None) or (
        location.max_entfernung_km if location else None
    )
    if max_km and location and location.plz:
        d = distance_km(location.plz, listing.standort_plz)
        if d is not None and d > max_km:
            return "entfernung"

    return None


def hard_filter(
    state: InterviewState, listings: Optional[Sequence[Listing]] = None
) -> tuple[list[Listing], FilterReport]:
    """Stage one. Boolean, deterministic, and it explains itself."""
    pool = list(listings if listings is not None else load_listings())
    survivors: list[Listing] = []
    dropped: dict[str, int] = {}

    for listing in pool:
        reason = _fails(listing, state)
        if reason is None:
            survivors.append(listing)
        else:
            dropped[reason] = dropped.get(reason, 0) + 1

    ordered = {k: dropped[k] for k in CONSTRAINT_ORDER if k in dropped}
    return survivors, FilterReport(gesamt=len(pool), uebrig=len(survivors), ausgeschlossen=ordered)


# ---------------------------------------------------------------- stage 2


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _relative(value: float, best: float, worst: float, lower_is_better: bool = True) -> float:
    """Place a value on a 0 to 100 scale against the candidate set."""
    if best == worst:
        return 50.0
    if lower_is_better:
        return _clamp(100.0 * (worst - value) / (worst - best))
    return _clamp(100.0 * (value - worst) / (best - worst))


def _einsatzzweck_score(listing: Listing, state: InterviewState) -> tuple[float, str]:
    """How well the vehicle suits what the person actually does with it."""
    from agent.state import UseCaseTag

    tags = set(state.use_case_tags.value or [])
    if not tags:
        return 50.0, "kein Einsatzzweck angegeben, neutral bewertet"

    scores: list[float] = []
    notes: list[str] = []

    if UseCaseTag.FAMILIE in tags:
        # INVENTED divisors. Two seats scores zero and seven scores full; 700 litres
        # is treated as a full boot. Both chosen by eye, not from segment data.
        seats = _clamp((listing.sitzplaetze - 2) / 5 * 100)
        boot = _clamp(listing.kofferraum_liter / 700 * 100)
        scores.append((seats + boot) / 2)
        notes.append(f"{listing.sitzplaetze} Sitze, {listing.kofferraum_liter} l Kofferraum")

    if UseCaseTag.UMZUG in tags:
        # INVENTED. 900 litres treated as a full load volume for a move.
        scores.append(_clamp(listing.kofferraum_liter / 900 * 100))
        notes.append(f"{listing.kofferraum_liter} l Ladevolumen")

    if UseCaseTag.STADTVERKEHR in tags:
        # INVENTED. Mass as a proxy for how easy a car is to place in a city, with
        # 900 kg as ideal and 2100 kg as worst. Mass is a proxy for footprint, which is
        # itself a proxy for parking; two removes from the thing actually being scored.
        compact = _clamp(100 - (listing.leermasse_kg - 900) / 1200 * 100)
        scores.append(compact)
        notes.append(f"{listing.leermasse_kg} kg Leermasse, stadttauglich")

    if UseCaseTag.PENDELN in tags or UseCaseTag.LANGSTRECKE in tags:
        if listing.ist_elektro:
            # INVENTED ceilings: 25 kWh and 12 l per 100 km treated as worst case.
            consumption = _clamp(100 - (listing.verbrauch_kwh_100km or 20) / 25 * 100)
            notes.append(f"{listing.verbrauch_kwh_100km} kWh/100 km")
        else:
            consumption = _clamp(100 - (listing.verbrauch_l_100km or 8) / 12 * 100)
            notes.append(f"{listing.verbrauch_l_100km} l/100 km")
        scores.append(consumption)

    if UseCaseTag.LANGSTRECKE in tags:
        # INVENTED. 150 kW treated as ample for long distance work.
        scores.append(_clamp(listing.leistung_kw / 150 * 100))

    if UseCaseTag.GEWERBLICH in tags and listing.listing_type == "kauf":
        scores.append(100.0 if listing.mwst_ausweisbar else 40.0)
        notes.append("MwSt. ausweisbar" if listing.mwst_ausweisbar else "MwSt. nicht ausweisbar")

    if not scores:
        return 50.0, "Einsatzzweck neutral"
    return sum(scores) / len(scores), "; ".join(notes) or "Einsatzzweck bewertet"


def _zustand_score(listing: Listing) -> tuple[float, str]:
    parts: list[float] = []
    notes: list[str] = []

    parts.append(100.0 if listing.unfallfrei else 0.0)
    notes.append("unfallfrei" if listing.unfallfrei else "Unfallschaden")

    # INVENTED. 25 points deducted per previous owner beyond the first.
    parts.append(_clamp(100 - (listing.vorbesitzer - 1) * 25))
    notes.append(f"{listing.vorbesitzer} Vorbesitzer")

    hu = listing.hu_monate_verbleibend()
    # INVENTED. A full 24 months until the next inspection scores full marks.
    parts.append(_clamp(hu / 24 * 100))
    notes.append(f"HU noch {max(hu, 0)} Monate" if hu > 0 else "HU fällig")

    return sum(parts) / len(parts), ", ".join(notes)


def score_listings(
    survivors: Sequence[Listing],
    state: InterviewState,
    tco_fn: Optional[Callable[[Listing, InterviewState], int]] = None,
) -> list[tuple[Listing, ScoreBreakdown, Optional[int]]]:
    """Stage two. Weighted sum over named dimensions, all relative to the survivors.

    `tco_fn` supplies five year cost of ownership. When absent, running cost falls
    back to consumption, which is a proxy rather than a substitute, and the
    justification text says so.
    """
    if not survivors:
        return []

    weights = state.weights()
    intent = state.effective_intent()
    ceiling = state.budget.value.ceiling_for(intent) if state.budget.value else None
    location = state.location.value

    costs: dict[str, float] = {}
    for listing in survivors:
        if tco_fn:
            costs[listing.id] = float(tco_fn(listing, state))
        else:
            base = listing.verbrauch_kwh_100km or listing.verbrauch_l_100km or 6.0
            costs[listing.id] = base * 1000

    prices = [float(l.preis_referenz()) for l in survivors]
    ages = [l.alter_jahre() for l in survivors]
    kms = [float(l.kilometerstand) for l in survivors]
    cost_values = [costs[l.id] for l in survivors]

    distances: dict[str, Optional[float]] = {}
    for listing in survivors:
        distances[listing.id] = (
            distance_km(location.plz, listing.standort_plz)
            if location and location.plz
            else None
        )
    known_distances = [d for d in distances.values() if d is not None]

    results: list[tuple[Listing, ScoreBreakdown, Optional[int]]] = []

    for listing in survivors:
        dims: list[DimensionScore] = []

        # Price headroom against the stated budget.
        if ceiling:
            # Linear in price, so the dimension stays strictly ordered. An earlier
            # version doubled the headroom, which saturated at 100 for anything under
            # half the budget and made every cheap car tie.
            headroom = (ceiling - listing.preis_referenz()) / ceiling
            raw = _clamp(headroom * 100)
            note = f"{listing.preis_referenz():,} EUR bei Budget {ceiling:,} EUR".replace(",", ".")
        else:
            raw = _relative(float(listing.preis_referenz()), min(prices), max(prices))
            note = f"{listing.preis_referenz():,} EUR, kein Budget genannt".replace(",", ".")
        dims.append(("preis", raw, note))

        # Five year running cost.
        raw = _relative(costs[listing.id], min(cost_values), max(cost_values))
        if tco_fn:
            note = f"{int(costs[listing.id]):,} EUR Gesamtkosten über fünf Jahre".replace(",", ".")
        else:
            unit = "kWh" if listing.ist_elektro else "l"
            base = listing.verbrauch_kwh_100km or listing.verbrauch_l_100km
            note = f"Verbrauch {base} {unit}/100 km, Näherung ohne Gesamtkostenrechnung"
        dims.append(("kosten", raw, note))

        # Age and mileage against the candidate set.
        age_score = _relative(listing.alter_jahre(), min(ages), max(ages))
        km_score = _relative(float(listing.kilometerstand), min(kms), max(kms))
        raw = (age_score + km_score) / 2
        note = (
            f"EZ {listing.erstzulassung}, "
            f"{format(listing.kilometerstand, ',').replace(',', '.')} km"
        )
        dims.append(("alter", raw, note))

        raw, note = _einsatzzweck_score(listing, state)
        dims.append(("zweck", raw, note))

        raw, note = _zustand_score(listing)
        dims.append(("zustand", raw, note))

        d = distances[listing.id]
        if d is None or not known_distances:
            raw, note = 50.0, "Entfernung unbekannt"
        else:
            raw = _relative(d, min(known_distances), max(known_distances))
            note = f"{d:.0f} km bis {listing.standort_ort}"
        dims.append(("entfernung", raw, note))

        keys = [
            Dimension.PREIS_SPIELRAUM,
            Dimension.GESAMTKOSTEN,
            Dimension.ALTER_LAUFLEISTUNG,
            Dimension.EINSATZZWECK,
            Dimension.ZUSTAND,
            Dimension.ENTFERNUNG,
        ]
        scored = [
            DimensionScore(
                name=key,
                label=DIMENSION_LABELS[key],
                gewicht=round(weights[key], 4),
                rohwert=round(raw_value, 2),
                beitrag=round(weights[key] * raw_value, 4),
                begruendung=note_text,
            )
            for key, (_, raw_value, note_text) in zip(keys, dims)
        ]
        breakdown = ScoreBreakdown(
            dimensionen=scored,
            total=round(sum(d.beitrag for d in scored), 2),
        )
        results.append((listing, breakdown, int(costs[listing.id]) if tco_fn else None))

    return results


def _compare(
    winner: tuple[Listing, ScoreBreakdown, Optional[int]],
    runner_up: tuple[Listing, ScoreBreakdown, Optional[int]],
) -> Comparison:
    a, a_score, a_cost = winner
    b, b_score, b_cost = runner_up
    return Comparison(
        gegen_id=b.id,
        gegen_bezeichnung=b.bezeichnung,
        punkte_vorsprung=round(a_score.total - b_score.total, 2),
        preis_differenz_eur=a.preis_referenz() - b.preis_referenz(),
        km_differenz=a.kilometerstand - b.kilometerstand,
        alter_differenz_jahre=round(a.alter_jahre() - b.alter_jahre(), 1),
        kosten_differenz_eur=(a_cost - b_cost) if (a_cost is not None and b_cost is not None) else None,
    )


def rank(
    state: InterviewState,
    listings: Optional[Sequence[Listing]] = None,
    limit: int = 5,
    tco_fn: Optional[Callable[[Listing, InterviewState], int]] = None,
) -> RankingResult:
    """The whole pipeline. Deterministic: same state and dataset, same output."""
    survivors, report = hard_filter(state, listings)
    scored = score_listings(survivors, state, tco_fn=tco_fn)

    # Sort by score, then by id, so ties never reorder between runs.
    scored.sort(key=lambda item: (-item[1].total, item[0].id))

    recommendations: list[Recommendation] = []
    for index, (listing, breakdown, cost) in enumerate(scored[:limit]):
        comparison = _compare(scored[index], scored[index + 1]) if index + 1 < len(scored) else None
        recommendations.append(
            Recommendation(
                listing=listing,
                score=breakdown,
                rang=index + 1,
                tco_gesamt_eur=cost,
                vergleich=comparison,
            )
        )

    return RankingResult(
        report=report,
        empfehlungen=recommendations,
        gewichte={d.value: round(w, 4) for d, w in state.weights().items()},
    )
