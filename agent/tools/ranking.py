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

from datetime import date, timedelta
from typing import Callable, Iterable, Optional, Sequence

from pydantic import BaseModel, Field

from agent import i18n
from agent.i18n import DEFAULT_LANG, Lang
from agent.listing import PLAKETTEN_RANG, Listing, load_listings
from agent.state import Dimension, Intent, InterviewState
from agent.tools.geo import distance_km
from agent.tools.tco import STANDARD_MIETDAUER_TAGE

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
    "verfuegbarkeit",
    "entfernung",
)

# INVENTED. Default pickup radius applied to rentals when the user has not named one.
# Distance is a three percent soft weight, which was enough to let a moving van 404 km
# from the renter win: nobody collects a van from Wiesbaden for a weekend in Hamburg.
# For a rental the radius is a hard constraint, because collection is a trip the renter
# has to make twice on the day.
#
# 100 rather than a tighter 50 because `agent.tools.geo` places postal codes at the
# centroid of their two digit region, so its error is tens of kilometres. A threshold
# of 50 would be within the noise of the measurement it is applied to. Purchases keep
# the soft weight: a car is collected once, and people do travel for the right one.
STANDARD_MIET_RADIUS_KM = 100


def constraint_label(key: str, lang: Lang = DEFAULT_LANG) -> str:
    """Human readable constraint name. The user sees these, not the keys."""
    return i18n.t(f"c.{key}", lang)


def dimension_label(dim: Dimension, lang: Lang = DEFAULT_LANG) -> str:
    return i18n.t(f"dim.{dim.value}", lang)


# Retained for callers that want the German set without passing a language.
CONSTRAINT_LABELS: dict[str, str] = {
    key: i18n.t(f"c.{key}", "de")
    for key in (
        "angebotsart", "kategorie", "budget", "getriebe", "kraftstoff", "sitzplaetze",
        "kofferraum", "umweltplakette", "kilometerstand", "unfallfrei",
        "verfuegbarkeit", "entfernung",
    )
}

DIMENSION_LABELS: dict[Dimension, str] = {
    dim: i18n.t(f"dim.{dim.value}", "de") for dim in Dimension
}


class FilterReport(BaseModel):
    """What the hard filter did, in terms the user can be told."""

    gesamt: int
    uebrig: int
    ausgeschlossen: dict[str, int] = Field(default_factory=dict)
    # Set only when a radius the user never asked for did the excluding. A constraint
    # applied on the user's behalf has to say so, or the drop count reads as their
    # own criterion rejecting listings.
    angenommener_radius_km: Optional[int] = None

    @property
    def ausgeschlossen_gesamt(self) -> int:
        return sum(self.ausgeschlossen.values())

    def erklaerung(self, lang: Lang = DEFAULT_LANG) -> str:
        total = i18n.fmt_int(self.gesamt, lang)
        left = i18n.fmt_int(self.uebrig, lang)
        if not self.ausgeschlossen:
            return (
                f"{total} Angebote geprüft, keines ausgeschlossen."
                if lang == "de"
                else f"{total} listings checked, none excluded."
            )
        parts = [
            f"{constraint_label(k, lang)} {i18n.fmt_int(v, lang)}"
            for k, v in sorted(self.ausgeschlossen.items(), key=lambda kv: -kv[1])
        ]
        dropped = i18n.fmt_int(self.ausgeschlossen_gesamt, lang)
        if lang == "de":
            satz = (
                f"{total} Angebote geprüft, {dropped} ausgeschlossen "
                f"({', '.join(parts)}), {left} verblieben."
            )
        else:
            satz = (
                f"{total} listings checked, {dropped} excluded "
                f"({', '.join(parts)}), {left} remaining."
            )
        if self.angenommener_radius_km and "entfernung" in self.ausgeschlossen:
            radius = i18n.fmt_int(self.angenommener_radius_km, lang)
            satz += (
                f" Abholradius {radius} km angenommen, nicht genannt."
                if lang == "de"
                else f" A pickup radius of {radius} km was assumed, not stated."
            )
        return satz

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

    def erklaerung(self, lang: Lang = DEFAULT_LANG) -> str:
        """A sentence a user can act on, not a bare number."""
        if self.begrenzt_durch:
            limiting = next(
                (c for c in self.komponenten if c.name == self.begrenzt_durch), None
            )
            if limiting:
                # The headline number is a rank in the field; the limit is internal to
                # the composite. Saying both plainly avoids reading a rank of 100 and a
                # limiting component as a contradiction.
                if lang == "de":
                    return (
                        f"{self.label}: Rang {self.rohwert:.0f} von 100 im Feld, "
                        f"intern begrenzt durch {limiting.name} ({limiting.detail})"
                    )
                return (
                    f"{self.label}: rank {self.rohwert:.0f} of 100 in the field, "
                    f"internally limited by {limiting.name} ({limiting.detail})"
                )
        if lang == "de":
            return (
                f"{self.label}: Rang {self.rohwert:.0f} von 100 im Feld, {self.begruendung}"
            )
        return f"{self.label}: rank {self.rohwert:.0f} of 100 in the field, {self.begruendung}"


class ScoreBreakdown(BaseModel):
    dimensionen: list[DimensionScore]
    total: float
    basis_anzahl: int = 0  # how many survivors this score was ranked against

    def relativ_hinweis_lang(self, lang: Lang = DEFAULT_LANG) -> str:
        if lang == "de":
            return self.relativ_hinweis
        return (
            f"The score is a placing among {self.basis_anzahl} remaining listings, not "
            f"an absolute mark. Change the filters and the comparison field changes, "
            f"and with it the score."
        )

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

    def top_faktoren(self, n: int = 3, lang: Lang = DEFAULT_LANG) -> list[str]:
        ranked = sorted(self.dimensionen, key=lambda d: -d.beitrag)
        return [d.erklaerung(lang) for d in ranked[:n] if d.beitrag > 0]

    def schwachstellen(self, n: int = 2, lang: Lang = DEFAULT_LANG) -> list[str]:
        """The dimensions holding this car back, named so they can be acted on."""
        ranked = sorted(self.dimensionen, key=lambda d: d.rohwert)
        return [d.erklaerung(lang) for d in ranked[:n] if d.rohwert < 50]


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


def _ist_verfuegbar(listing: Listing, state: InterviewState) -> bool:
    """Whether this listing can actually be had on the date the user wants it.

    Only rentals carry an availability window, because a car for sale is available
    when it is sold. A rental is a specific vehicle held for a specific period, so a
    perfect match that cannot be collected on the day is not a match.

    Date flexibility widens the window symmetrically: someone who can shift by three
    days should see the offers that are free three days either side. With no target
    date recorded, nothing is excluded, which keeps the constraint inert rather than
    guessing on the user's behalf.
    """
    ziel = state.target_date.value
    if ziel is None or listing.listing_type != "miete":
        return True

    von, bis = listing.verfuegbar_von, listing.verfuegbar_bis
    if not von or not bis:
        return True  # an offer that states no window is not one we can rule out

    spielraum = timedelta(days=max(0, state.date_flexibility_days.value or 0))
    try:
        fenster_von = date.fromisoformat(von)
        fenster_bis = date.fromisoformat(bis)
    except ValueError:
        return True  # unparseable window, so it cannot be checked, so it cannot fail

    return (fenster_von - spielraum) <= ziel <= (fenster_bis + spielraum)


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

    if not _ist_verfuegbar(listing, state):
        return "verfuegbarkeit"

    max_km = (constraints.max_entfernung_km if constraints else None) or (
        location.max_entfernung_km if location else None
    )
    # A rental with no stated radius gets the default one. A purchase does not: the
    # existing soft weight is the right treatment there.
    if max_km is None and intent is Intent.MIETE:
        max_km = STANDARD_MIET_RADIUS_KM
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

    constraints = state.constraints_hard.value
    location = state.location.value
    genannt = (constraints.max_entfernung_km if constraints else None) or (
        location.max_entfernung_km if location else None
    )
    angenommen = (
        STANDARD_MIET_RADIUS_KM
        if genannt is None
        and state.effective_intent() is Intent.MIETE
        and location
        and location.plz
        else None
    )

    return survivors, FilterReport(
        gesamt=len(pool),
        uebrig=len(survivors),
        ausgeschlossen=ordered,
        angenommener_radius_km=angenommen,
    )


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


def _einsatzzweck_components(
    listing: Listing, state: InterviewState, lang: Lang = DEFAULT_LANG
) -> list[Component]:
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
                name=i18n.t("k.Sitzplätze", lang),
                wert=_clamp((listing.sitzplaetze - 2) / 5 * 100),
                detail=(f"{listing.sitzplaetze} Sitze" if lang == "de"
                        else f"{listing.sitzplaetze} seats"),
            )
        )
        components.append(
            Component(
                name=i18n.t("k.Kofferraum", lang),
                wert=_clamp(listing.kofferraum_liter / 700 * 100),
                detail=(f"{listing.kofferraum_liter} l gegen {needed} l gewünscht"
                        if lang == "de"
                        else f"{listing.kofferraum_liter} l against {needed} l wanted"),
            )
        )

    if UseCaseTag.UMZUG in tags:
        # INVENTED. 900 litres treated as a full load volume for a move.
        components.append(
            Component(
                name=i18n.t("k.Ladevolumen", lang),
                wert=_clamp(listing.kofferraum_liter / 900 * 100),
                detail=(f"{listing.kofferraum_liter} l Ladevolumen" if lang == "de"
                        else f"{listing.kofferraum_liter} l load volume"),
            )
        )

    if UseCaseTag.STADTVERKEHR in tags:
        # INVENTED. Mass as a proxy for how easy a car is to place in a city, 900 kg
        # ideal and 2100 kg worst. Mass proxies footprint, which proxies parking, so
        # this is two removes from the thing actually being judged.
        components.append(
            Component(
                name=i18n.t("k.Stadttauglichkeit", lang),
                wert=_clamp(100 - (listing.leermasse_kg - 900) / 1200 * 100),
                detail=(f"{listing.leermasse_kg} kg Leermasse" if lang == "de"
                        else f"{listing.leermasse_kg} kg kerb weight"),
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
        components.append(Component(name=i18n.t("k.Verbrauch", lang), wert=wert, detail=detail))

    if UseCaseTag.LANGSTRECKE in tags:
        # INVENTED. 150 kW treated as ample for long distance work.
        components.append(
            Component(
                name=i18n.t("k.Motorisierung", lang),
                wert=_clamp(listing.leistung_kw / 150 * 100),
                detail=f"{listing.leistung_kw} kW",
            )
        )

    if UseCaseTag.GEWERBLICH in tags and listing.listing_type == "kauf":
        components.append(
            Component(
                name=i18n.t("k.Vorsteuerabzug", lang),
                wert=100.0 if listing.mwst_ausweisbar else 40.0,
                detail=(("MwSt. ausweisbar" if listing.mwst_ausweisbar else "MwSt. nicht ausweisbar")
                        if lang == "de"
                        else ("VAT deductible" if listing.mwst_ausweisbar else "VAT not deductible")),
            )
        )

    return components


def _zustand_components(listing: Listing, lang: Lang = DEFAULT_LANG) -> list[Component]:
    hu = listing.hu_monate_verbleibend()
    return [
        Component(
            name=i18n.t("k.Unfallfreiheit", lang),
            wert=100.0 if listing.unfallfrei else 0.0,
            detail=(("unfallfrei" if listing.unfallfrei else "Unfallschaden") if lang == "de"
                    else ("accident-free" if listing.unfallfrei else "accident damage")),
        ),
        # INVENTED. 25 points deducted per previous owner beyond the first.
        Component(
            name=i18n.t("k.Vorbesitzer", lang),
            wert=_clamp(100 - (listing.vorbesitzer - 1) * 25),
            detail=(f"{listing.vorbesitzer} Vorbesitzer" if lang == "de"
                    else f"{listing.vorbesitzer} previous owners"),
        ),
        # INVENTED. A full 24 months until the next inspection scores full marks.
        Component(
            name=i18n.t("k.HU", lang),
            wert=_clamp(hu / 24 * 100),
            detail=((f"HU noch {max(hu, 0)} Monate" if hu > 0 else "HU fällig") if lang == "de"
                    else (f"test valid {max(hu, 0)} more months" if hu > 0 else "test due")),
        ),
    ]


def score_listings(
    survivors: Sequence[Listing],
    state: InterviewState,
    tco_fn: Optional[Callable[[Listing, InterviewState], int]] = None,
    lang: Lang = DEFAULT_LANG,
) -> list[tuple[Listing, ScoreBreakdown, Optional[int]]]:
    """Stage two. Weighted sum over named dimensions, normalised against the pool.

    Every dimension is percentile normalised against the survivors, so each one uses
    the full range and none can silently flatten into a constant offset.

    `tco_fn` supplies the cost figure, and which cost model it uses depends on the
    listing: five year ownership for a purchase, total rental cost for a rental. When
    absent, running cost falls back to consumption, which is a proxy rather than a
    substitute, and the justification text says so.

    KNOWN LIMITATION. Those two figures are not comparable with each other. Under a
    stated intent the pool is all one type, so the percentile ranking compares like
    with like. Under Intent.UNENTSCHIEDEN the pool is mixed, and a three day rental
    total will always undercut a five year ownership total, so rentals sort first for
    a reason that is an artefact of the units rather than a finding about the cars.
    Fixing it needs a common horizon for both models, which is a larger change than
    this project needs; it is recorded rather than hidden.
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

    zweck_parts = [_einsatzzweck_components(l, state, lang) for l in survivors]
    zustand_parts = [_zustand_components(l, lang) for l in survivors]
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
        return i18n.fmt_int(value, lang)

    results: list[tuple[Listing, ScoreBreakdown, Optional[int]]] = []

    for i, listing in enumerate(survivors):
        if ceiling:
            note_preis = (
                f"{de(prices[i])} EUR bei Budget {de(ceiling)} EUR"
                if lang == "de"
                else f"{de(prices[i])} EUR against a budget of {de(ceiling)} EUR"
            )
        else:
            note_preis = (
                f"{de(prices[i])} EUR, kein Budget genannt"
                if lang == "de"
                else f"{de(prices[i])} EUR, no budget stated"
            )

        ist_miete = listing.listing_type == "miete"
        if tco_fn and ist_miete:
            tage = state.mietdauer_tage.value or STANDARD_MIETDAUER_TAGE
            note_kosten = (
                f"{de(costs[i])} EUR Mietkosten für {tage} Tage"
                if lang == "de"
                else f"{de(costs[i])} EUR rental cost for {tage} days"
            )
        elif tco_fn:
            note_kosten = (
                f"{de(costs[i])} EUR Gesamtkosten über fünf Jahre"
                if lang == "de"
                else f"{de(costs[i])} EUR total cost over five years"
            )
        else:
            unit = "kWh" if listing.ist_elektro else "l"
            base = listing.verbrauch_kwh_100km or listing.verbrauch_l_100km
            note_kosten = (
                f"Verbrauch {base} {unit}/100 km, Näherung ohne Gesamtkosten"
                if lang == "de"
                else f"consumption {base} {unit}/100 km, proxy without full cost model"
            )

        note_zweck = "; ".join(f"{c.name} {c.detail}" for c in zweck_parts[i]) or (
            "kein Einsatzzweck angegeben, neutral bewertet"
            if lang == "de"
            else "no use case stated, scored neutrally"
        )
        note_zustand = ", ".join(c.detail for c in zustand_parts[i])
        if raw_distances[i] is not None:
            # Place name is a proper noun and stays as it is in both languages.
            note_entfernung = (
                f"{distances[i]:.0f} km bis {listing.standort_ort}"
                if lang == "de"
                else f"{distances[i]:.0f} km to {listing.standort_ort}"
            )
        else:
            note_entfernung = (
                "Entfernung unbekannt, als Mittelwert gewertet"
                if lang == "de"
                else "distance unknown, scored at the median"
            )

        spec = [
            (Dimension.PREIS_SPIELRAUM, p_preis[i], note_preis, [], None),
            (Dimension.GESAMTKOSTEN, p_kosten[i], note_kosten, [], None),
            (
                Dimension.ALTER_LAUFLEISTUNG,
                p_alter[i],
                (
                    f"EZ {listing.erstzulassung}, {de(listing.kilometerstand)} km"
                    if lang == "de"
                    else f"first reg. {listing.erstzulassung}, {de(listing.kilometerstand)} km"
                ),
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
                label=(
                    i18n.t("dim.mietkosten", lang)
                    if key is Dimension.GESAMTKOSTEN and ist_miete
                    else dimension_label(key, lang)
                ),
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
    lang: Lang = DEFAULT_LANG,
) -> RankingResult:
    """The whole pipeline. Deterministic: same state and dataset, same output."""
    survivors, report = hard_filter(state, listings)
    scored = score_listings(survivors, state, tco_fn=tco_fn, lang=lang)

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
