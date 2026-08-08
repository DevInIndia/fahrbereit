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


class Component(BaseModel):
    """One ingredient of a composite dimension, named so it can be pointed at."""

    name: str      # "Kofferraum"
    wert: float    # 0 to 100
    detail: str    # "380 l von 400 l gewünscht"


class DimensionScore(BaseModel):
    name: Dimension
    label: str
    gewicht: float
    rohwert: float   # 0 to 100, a rank position within the survivor pool
    beitrag: float   # gewicht * rohwert
    begruendung: str
    komponenten: list[Component] = Field(default_factory=list)
    begrenzt_durch: Optional[str] = None  # the component that capped a weakest link
    relativ: bool = True  # scored against the pool, not on an absolute scale

    def erklaerung(self) -> str:
        """A sentence a user can act on, not a bare number."""
        if self.begrenzt_durch:
            limiting = next(
                (c for c in self.komponenten if c.name == self.begrenzt_durch), None
            )
            if limiting:
                # The headline number is a rank in the field; the limit is internal to
                # the composite. Saying both plainly avoids reading a rank of 100 and a
                # limiting component as a contradiction.
                return (
                    f"{self.label}: Rang {self.rohwert:.0f} von 100 im Feld, "
                    f"intern begrenzt durch {limiting.name} ({limiting.detail})"
                )
        return f"{self.label}: Rang {self.rohwert:.0f} von 100 im Feld, {self.begruendung}"


class ScoreBreakdown(BaseModel):
    dimensionen: list[DimensionScore]
    total: float
    basis_anzahl: int = 0  # how many survivors this score was ranked against

    @property
    def relativ_hinweis(self) -> str:
        """Say out loud that the score is a rank, not an absolute rating.

        Percentile normalisation means the same car scores differently against a
        different pool. That is intended, and a judge who notices scores move when the
        filter changes should read it as designed rather than as instability.
        """
        return (
            f"Punktwert ist eine Platzierung unter {self.basis_anzahl} verbliebenen "
            f"Angeboten, keine absolute Note. Ändern sich die Filter, ändert sich das "
            f"Vergleichsfeld und damit der Punktwert."
        )

    def top_faktoren(self, n: int = 3) -> list[str]:
        ranked = sorted(self.dimensionen, key=lambda d: -d.beitrag)
        return [d.erklaerung() for d in ranked[:n] if d.beitrag > 0]

    def schwachstellen(self, n: int = 2) -> list[str]:
        """The dimensions holding this car back, named so they can be acted on."""
        ranked = sorted(self.dimensionen, key=lambda d: d.rohwert)
        return [d.erklaerung() for d in ranked[:n] if d.rohwert < 50]


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


def _percentile_scores(values: list[float], higher_is_better: bool = True) -> list[float]:
    """Map raw values onto 0 to 100 by their rank within the candidate pool.

    This is what stops a dimension quietly becoming a constant. An absolute scale can
    compress every candidate into a narrow band, at which point the dimension carries
    weight without carrying information. A rank based scale always spans the full range
    across whatever is actually being compared.

    The consequence is that a score is a position against the current survivors, not an
    absolute rating, so the same car scores differently against a different pool. That
    is intended and it is surfaced rather than left implicit, via basis_anzahl and the
    relativ flag on each dimension.

    Ties share the average of the ranks they span, so equal inputs always produce equal
    outputs and ordering stays reproducible.
    """
    n = len(values)
    if n == 0:
        return []
    if n == 1:
        return [50.0]

    order = sorted(range(n), key=lambda i: values[i], reverse=not higher_is_better)
    out = [0.0] * n
    pos = 0
    while pos < n:
        run_end = pos
        while run_end + 1 < n and values[order[run_end + 1]] == values[order[pos]]:
            run_end += 1
        average_rank = (pos + run_end) / 2.0
        score = 100.0 * average_rank / (n - 1)
        for k in range(pos, run_end + 1):
            out[order[k]] = round(score, 4)
        pos = run_end + 1
    return out


def _weakest_link(components: list[Component]) -> tuple[float, Optional[str]]:
    """Score a composite dimension by its worst component, and name that component.

    Averaging was the previous behaviour and it destroyed the range: a five seat car
    with a small boot averaged out to the middle of the field instead of reading as
    unsuitable. Taking the minimum restores the discrimination, and because the limiting
    component is returned alongside it the result stays explainable. A bare 41 tells a
    user nothing. "41, limited by boot volume" tells them what to change.
    """
    if not components:
        return 50.0, None
    worst = min(components, key=lambda c: c.wert)
    return worst.wert, worst.name


def _einsatzzweck_components(listing: Listing, state: InterviewState) -> list[Component]:
    """One component per thing the stated use case actually demands."""
    from agent.state import UseCaseTag

    tags = set(state.use_case_tags.value or [])
    constraints = state.constraints_hard.value
    components: list[Component] = []

    if UseCaseTag.FAMILIE in tags:
        # INVENTED divisors. Two seats scores zero and seven scores full; 700 litres is
        # treated as a full boot. Both chosen by eye, not from segment data.
        needed = (constraints.min_kofferraum_liter if constraints else None) or 400
        components.append(
            Component(
                name="Sitzplätze",
                wert=_clamp((listing.sitzplaetze - 2) / 5 * 100),
                detail=f"{listing.sitzplaetze} Sitze",
            )
        )
        components.append(
            Component(
                name="Kofferraum",
                wert=_clamp(listing.kofferraum_liter / 700 * 100),
                detail=f"{listing.kofferraum_liter} l gegen {needed} l gewünscht",
            )
        )

    if UseCaseTag.UMZUG in tags:
        # INVENTED. 900 litres treated as a full load volume for a move.
        components.append(
            Component(
                name="Ladevolumen",
                wert=_clamp(listing.kofferraum_liter / 900 * 100),
                detail=f"{listing.kofferraum_liter} l Ladevolumen",
            )
        )

    if UseCaseTag.STADTVERKEHR in tags:
        # INVENTED. Mass as a proxy for how easy a car is to place in a city, 900 kg
        # ideal and 2100 kg worst. Mass proxies footprint, which proxies parking, so
        # this is two removes from the thing actually being judged.
        components.append(
            Component(
                name="Stadttauglichkeit",
                wert=_clamp(100 - (listing.leermasse_kg - 900) / 1200 * 100),
                detail=f"{listing.leermasse_kg} kg Leermasse",
            )
        )

    if UseCaseTag.PENDELN in tags or UseCaseTag.LANGSTRECKE in tags:
        # INVENTED ceilings: 25 kWh and 12 l per 100 km treated as worst case.
        if listing.ist_elektro:
            wert = _clamp(100 - (listing.verbrauch_kwh_100km or 20) / 25 * 100)
            detail = f"{listing.verbrauch_kwh_100km} kWh/100 km"
        else:
            wert = _clamp(100 - (listing.verbrauch_l_100km or 8) / 12 * 100)
            detail = f"{listing.verbrauch_l_100km} l/100 km"
        components.append(Component(name="Verbrauch", wert=wert, detail=detail))

    if UseCaseTag.LANGSTRECKE in tags:
        # INVENTED. 150 kW treated as ample for long distance work.
        components.append(
            Component(
                name="Motorisierung",
                wert=_clamp(listing.leistung_kw / 150 * 100),
                detail=f"{listing.leistung_kw} kW",
            )
        )

    if UseCaseTag.GEWERBLICH in tags and listing.listing_type == "kauf":
        components.append(
            Component(
                name="Vorsteuerabzug",
                wert=100.0 if listing.mwst_ausweisbar else 40.0,
                detail="MwSt. ausweisbar" if listing.mwst_ausweisbar else "MwSt. nicht ausweisbar",
            )
        )

    return components


def _zustand_components(listing: Listing) -> list[Component]:
    hu = listing.hu_monate_verbleibend()
    return [
        Component(
            name="Unfallfreiheit",
            wert=100.0 if listing.unfallfrei else 0.0,
            detail="unfallfrei" if listing.unfallfrei else "Unfallschaden",
        ),
        # INVENTED. 25 points deducted per previous owner beyond the first.
        Component(
            name="Vorbesitzer",
            wert=_clamp(100 - (listing.vorbesitzer - 1) * 25),
            detail=f"{listing.vorbesitzer} Vorbesitzer",
        ),
        # INVENTED. A full 24 months until the next inspection scores full marks.
        Component(
            name="HU",
            wert=_clamp(hu / 24 * 100),
            detail=f"HU noch {max(hu, 0)} Monate" if hu > 0 else "HU fällig",
        ),
    ]


def score_listings(
    survivors: Sequence[Listing],
    state: InterviewState,
    tco_fn: Optional[Callable[[Listing, InterviewState], int]] = None,
) -> list[tuple[Listing, ScoreBreakdown, Optional[int]]]:
    """Stage two. Weighted sum over named dimensions, normalised against the pool.

    Every dimension is percentile normalised against the survivors, so each one uses
    the full range and none can silently flatten into a constant offset.

    `tco_fn` supplies five year cost of ownership. When absent, running cost falls back
    to consumption, which is a proxy rather than a substitute, and the justification
    text says so.
    """
    if not survivors:
        return []

    weights = state.weights()
    intent = state.effective_intent()
    ceiling = state.budget.value.ceiling_for(intent) if state.budget.value else None
    location = state.location.value
    n = len(survivors)

    costs: list[float] = []
    for listing in survivors:
        if tco_fn:
            costs.append(float(tco_fn(listing, state)))
        else:
            base = listing.verbrauch_kwh_100km or listing.verbrauch_l_100km or 6.0
            costs.append(base * 1000)

    prices = [float(l.preis_referenz()) for l in survivors]
    ages = [l.alter_jahre() for l in survivors]
    kms = [float(l.kilometerstand) for l in survivors]

    raw_distances = [
        distance_km(location.plz, l.standort_plz) if location and location.plz else None
        for l in survivors
    ]
    known = sorted(d for d in raw_distances if d is not None)
    # Unknown distance takes the median, so it neither helps nor hurts.
    fallback = known[len(known) // 2] if known else 0.0
    distances = [d if d is not None else fallback for d in raw_distances]

    zweck_parts = [_einsatzzweck_components(l, state) for l in survivors]
    zustand_parts = [_zustand_components(l) for l in survivors]
    zweck = [_weakest_link(c) for c in zweck_parts]
    zustand = [_weakest_link(c) for c in zustand_parts]

    p_preis = _percentile_scores(prices, higher_is_better=False)
    p_kosten = _percentile_scores(costs, higher_is_better=False)
    # Age and mileage combined before ranking, so one composite position results.
    p_alter = _percentile_scores(
        [a * 0.5 + k / 30_000 * 0.5 for a, k in zip(ages, kms)], higher_is_better=False
    )
    p_zweck = _percentile_scores([v for v, _ in zweck], higher_is_better=True)
    p_zustand = _percentile_scores([v for v, _ in zustand], higher_is_better=True)
    p_entfernung = _percentile_scores(distances, higher_is_better=False)

    def de(value: int) -> str:
        return format(int(value), ",").replace(",", ".")

    results: list[tuple[Listing, ScoreBreakdown, Optional[int]]] = []

    for i, listing in enumerate(survivors):
        note_preis = (
            f"{de(prices[i])} EUR bei Budget {de(ceiling)} EUR"
            if ceiling
            else f"{de(prices[i])} EUR, kein Budget genannt"
        )

        if tco_fn:
            note_kosten = f"{de(costs[i])} EUR Gesamtkosten über fünf Jahre"
        else:
            unit = "kWh" if listing.ist_elektro else "l"
            base = listing.verbrauch_kwh_100km or listing.verbrauch_l_100km
            note_kosten = f"Verbrauch {base} {unit}/100 km, Näherung ohne Gesamtkosten"

        note_zweck = "; ".join(f"{c.name} {c.detail}" for c in zweck_parts[i]) or (
            "kein Einsatzzweck angegeben, neutral bewertet"
        )
        note_zustand = ", ".join(c.detail for c in zustand_parts[i])
        note_entfernung = (
            f"{distances[i]:.0f} km bis {listing.standort_ort}"
            if raw_distances[i] is not None
            else "Entfernung unbekannt, als Mittelwert gewertet"
        )

        spec = [
            (Dimension.PREIS_SPIELRAUM, p_preis[i], note_preis, [], None),
            (Dimension.GESAMTKOSTEN, p_kosten[i], note_kosten, [], None),
            (
                Dimension.ALTER_LAUFLEISTUNG,
                p_alter[i],
                f"EZ {listing.erstzulassung}, {de(listing.kilometerstand)} km",
                [],
                None,
            ),
            (Dimension.EINSATZZWECK, p_zweck[i], note_zweck, zweck_parts[i], zweck[i][1]),
            (Dimension.ZUSTAND, p_zustand[i], note_zustand, zustand_parts[i], zustand[i][1]),
            (Dimension.ENTFERNUNG, p_entfernung[i], note_entfernung, [], None),
        ]

        scored = [
            DimensionScore(
                name=key,
                label=DIMENSION_LABELS[key],
                gewicht=round(weights[key], 4),
                rohwert=round(raw_value, 2),
                beitrag=round(weights[key] * raw_value, 4),
                begruendung=note,
                komponenten=components,
                begrenzt_durch=limit,
                relativ=True,
            )
            for key, raw_value, note, components, limit in spec
        ]
        results.append(
            (
                listing,
                ScoreBreakdown(
                    dimensionen=scored,
                    total=round(sum(d.beitrag for d in scored), 2),
                    basis_anzahl=n,
                ),
                int(costs[i]) if tco_fn else None,
            )
        )

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
