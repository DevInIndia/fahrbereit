"""The ranking pipeline. Determinism, constraint satisfaction, and arithmetic."""

from __future__ import annotations

from datetime import date

import pytest

from agent.listing import load_listings
from agent.state import (
    Budget,
    Dimension,
    HardConstraints,
    Intent,
    InterviewState,
    Location,
    UseCaseTag,
)
from agent.tools.geo import distance_km
from agent.tools.ranking import (
    CONSTRAINT_ORDER,
    STANDARD_MIET_RADIUS_KM,
    hard_filter,
    rank,
    score_listings,
)
from agent.tools.tco import STANDARD_MIETDAUER_TAGE, rental_cost, tco_for_state


@pytest.fixture
def listings():
    return load_listings()


def family_state() -> InterviewState:
    st = InterviewState()
    st.intent = st.intent.state(Intent.KAUF)
    st.budget = st.budget.state(Budget(max_kaufpreis_eur=25000))
    st.use_case_tags = st.use_case_tags.state([UseCaseTag.FAMILIE, UseCaseTag.PENDELN])
    st.constraints_hard = st.constraints_hard.state(
        HardConstraints(unfallfrei_erforderlich=True, umweltplakette="grün")
    )
    st.location = st.location.state(Location(plz="80339", ort="München"))
    st.jahresfahrleistung_km = st.jahresfahrleistung_km.state(15000)
    return st


# ------------------------------------------------------------------ hard filter


def test_no_recommendation_violates_a_hard_constraint(listings):
    """SC-001. The one result that must never regress."""
    st = family_state()
    result = rank(st, listings, limit=20)
    for rec in result.empfehlungen:
        assert rec.listing.listing_type == "kauf"
        assert rec.listing.preis_referenz() <= 25000
        assert rec.listing.unfallfrei
        assert rec.listing.umweltplakette == "grün"


def test_drop_counts_sum_to_the_number_excluded(listings):
    st = family_state()
    survivors, report = hard_filter(st, listings)
    assert report.gesamt == len(listings)
    assert report.uebrig == len(survivors)
    assert report.ausgeschlossen_gesamt == report.gesamt - report.uebrig


def test_each_exclusion_is_attributed_to_exactly_one_constraint(listings):
    st = family_state()
    _, report = hard_filter(st, listings)
    assert set(report.ausgeschlossen).issubset(set(CONSTRAINT_ORDER))


def test_drop_counts_are_reported_in_a_fixed_order(listings):
    st = family_state()
    _, report = hard_filter(st, listings)
    keys = list(report.ausgeschlossen)
    positions = [CONSTRAINT_ORDER.index(k) for k in keys]
    assert positions == sorted(positions)


def test_transmission_constraint_excludes_manuals(listings):
    st = InterviewState()
    st.intent = st.intent.state(Intent.KAUF)
    st.constraints_hard = st.constraints_hard.state(HardConstraints(getriebe="Automatik"))
    survivors, report = hard_filter(st, listings)
    assert survivors
    assert all(l.getriebe == "Automatik" for l in survivors)
    assert report.ausgeschlossen.get("getriebe", 0) > 0


def test_seat_constraint_excludes_small_cars(listings):
    st = InterviewState()
    st.intent = st.intent.state(Intent.KAUF)
    st.constraints_hard = st.constraints_hard.state(HardConstraints(min_sitzplaetze=7))
    survivors, _ = hard_filter(st, listings)
    assert all(l.sitzplaetze >= 7 for l in survivors)


def test_green_badge_requirement_excludes_yellow_badges(listings):
    st = InterviewState()
    st.intent = st.intent.state(Intent.KAUF)
    st.constraints_hard = st.constraints_hard.state(HardConstraints(umweltplakette="grün"))
    survivors, report = hard_filter(st, listings)
    yellow = sum(1 for l in listings if l.listing_type == "kauf" and l.umweltplakette != "grün")
    assert all(l.umweltplakette == "grün" for l in survivors)
    assert report.ausgeschlossen.get("umweltplakette", 0) == yellow


def test_rental_intent_returns_only_rentals(listings):
    st = InterviewState()
    st.intent = st.intent.state(Intent.MIETE)
    survivors, _ = hard_filter(st, listings)
    assert survivors
    assert all(l.listing_type == "miete" for l in survivors)


def test_impossible_constraints_return_nothing_and_name_the_culprit(listings):
    st = InterviewState()
    st.intent = st.intent.state(Intent.KAUF)
    st.budget = st.budget.state(Budget(max_kaufpreis_eur=1))
    survivors, report = hard_filter(st, listings)
    assert survivors == []
    assert report.uebrig == 0
    assert report.groesster_ausschluss() == "budget"


def test_empty_result_does_not_crash_the_pipeline(listings):
    st = InterviewState()
    st.intent = st.intent.state(Intent.KAUF)
    st.budget = st.budget.state(Budget(max_kaufpreis_eur=1))
    result = rank(st, listings)
    assert result.empfehlungen == []
    assert "verblieben" in result.report.erklaerung()


# ------------------------------------------------------------------ scoring


def test_contributions_sum_to_the_reported_total(listings):
    """SC-005. A score the user cannot reconcile is a score they cannot trust."""
    result = rank(family_state(), listings, limit=10)
    assert result.empfehlungen
    for rec in result.empfehlungen:
        assert sum(d.beitrag for d in rec.score.dimensionen) == pytest.approx(
            rec.score.total, abs=0.01
        )


def test_weights_used_in_scoring_sum_to_one(listings):
    result = rank(family_state(), listings)
    assert sum(result.gewichte.values()) == pytest.approx(1.0, abs=0.001)


def test_every_dimension_appears_in_every_breakdown(listings):
    result = rank(family_state(), listings, limit=5)
    for rec in result.empfehlungen:
        assert {d.name for d in rec.score.dimensionen} == set(Dimension)


def test_every_dimension_carries_a_justification(listings):
    result = rank(family_state(), listings, limit=5)
    for rec in result.empfehlungen:
        for dim in rec.score.dimensionen:
            assert dim.begruendung.strip()


def test_scores_stay_within_range(listings):
    result = rank(family_state(), listings, limit=10)
    for rec in result.empfehlungen:
        assert 0.0 <= rec.score.total <= 100.0
        for dim in rec.score.dimensionen:
            assert 0.0 <= dim.rohwert <= 100.0


# ------------------------------------------------------------------ determinism


def test_identical_state_and_dataset_reproduce_identical_output(listings):
    """SC-004. Run it twice, get the same answer, or none of this is auditable."""
    first = rank(family_state(), listings, limit=10)
    second = rank(family_state(), listings, limit=10)
    assert [r.listing.id for r in first.empfehlungen] == [
        r.listing.id for r in second.empfehlungen
    ]
    assert [r.score.total for r in first.empfehlungen] == [
        r.score.total for r in second.empfehlungen
    ]


def test_ordering_is_stable_when_scores_tie(listings):
    """Ties break on id, so equal scores never shuffle between runs."""
    st = family_state()
    st.preferences_soft = st.preferences_soft.state({Dimension.ENTFERNUNG.value: 1.0})
    ids = [rank(st, listings, limit=10).empfehlungen[i].listing.id for i in range(3)]
    for _ in range(3):
        again = rank(st, listings, limit=10)
        assert [r.listing.id for r in again.empfehlungen][:3] == ids


def test_results_are_ordered_by_descending_score(listings):
    result = rank(family_state(), listings, limit=10)
    totals = [r.score.total for r in result.empfehlungen]
    assert totals == sorted(totals, reverse=True)


def test_ranks_are_sequential_from_one(listings):
    result = rank(family_state(), listings, limit=5)
    assert [r.rang for r in result.empfehlungen] == list(range(1, len(result.empfehlungen) + 1))


# ------------------------------------------------------------------ weights


def test_changing_weights_can_change_the_order(listings):
    """The weight control is only meaningful if it actually moves the list."""
    cheap = family_state()
    cheap.preferences_soft = cheap.preferences_soft.state(
        {Dimension.PREIS_SPIELRAUM.value: 1.0}
    )
    roomy = family_state()
    roomy.preferences_soft = roomy.preferences_soft.state({Dimension.EINSATZZWECK.value: 1.0})

    cheapest = rank(cheap, listings).empfehlungen[0].listing
    roomiest = rank(roomy, listings).empfehlungen[0].listing

    assert cheapest.preis_referenz() <= roomiest.preis_referenz()
    assert roomiest.kofferraum_liter >= cheapest.kofferraum_liter


def test_price_weighting_puts_the_cheapest_survivor_first(listings):
    """Price headroom must stay strictly ordered rather than saturating."""
    st = family_state()
    st.preferences_soft = st.preferences_soft.state({Dimension.PREIS_SPIELRAUM.value: 1.0})
    survivors, _ = hard_filter(st, listings)
    result = rank(st, listings, limit=len(survivors))
    assert result.empfehlungen[0].listing.preis_referenz() == min(
        l.preis_referenz() for l in survivors
    )


def test_price_headroom_does_not_saturate(listings):
    """Two listings well under budget must still separate on price."""
    st = family_state()
    st.preferences_soft = st.preferences_soft.state({Dimension.PREIS_SPIELRAUM.value: 1.0})
    survivors, _ = hard_filter(st, listings)
    # Distinct prices only. Two listings at the same price scoring the same is
    # correct, so including them would test nothing.
    by_price: dict[int, object] = {}
    for l in sorted(survivors, key=lambda l: l.preis_referenz()):
        by_price.setdefault(l.preis_referenz(), l)
    cheap = list(by_price.values())[:5]
    assert len(cheap) == 5

    result = rank(st, cheap, limit=5)
    totals = [r.score.total for r in result.empfehlungen]
    assert len(set(totals)) == len(totals), f"scores tied where they should differ: {totals}"


# ------------------------------------------------------------------ comparison


def test_the_winner_is_compared_against_the_runner_up(listings):
    result = rank(family_state(), listings, limit=5)
    top = result.empfehlungen[0]
    assert top.vergleich is not None
    assert top.vergleich.gegen_id == result.empfehlungen[1].listing.id
    assert top.vergleich.punkte_vorsprung >= 0


def test_the_last_recommendation_has_nothing_left_to_compare_against(listings):
    st = family_state()
    survivors, _ = hard_filter(st, listings)
    result = rank(st, listings, limit=len(survivors))
    assert len(result.empfehlungen) == len(survivors)
    assert result.empfehlungen[-1].vergleich is None


def test_comparison_deltas_match_the_underlying_listings(listings):
    result = rank(family_state(), listings, limit=5)
    first, second = result.empfehlungen[0], result.empfehlungen[1]
    expected = first.listing.preis_referenz() - second.listing.preis_referenz()
    assert first.vergleich.preis_differenz_eur == expected


def test_top_factors_are_drawn_from_the_score_data(listings):
    """Narration must come from the breakdown, never from the model's imagination.

    Each factor names a real dimension and quotes either that dimension's own
    justification or the detail of the component that limited it. Nothing else may
    appear, because anything else would be text the model could not verify.
    """
    result = rank(family_state(), listings, limit=3)
    for rec in result.empfehlungen:
        labels = {d.label for d in rec.score.dimensionen}
        details = {d.begruendung for d in rec.score.dimensionen}
        for dim in rec.score.dimensionen:
            details.update(c.detail for c in dim.komponenten)

        for factor in rec.score.top_faktoren():
            assert any(factor.startswith(label) for label in labels), factor
            assert any(detail in factor for detail in details), factor


def test_a_limited_dimension_names_the_component_that_limited_it(listings):
    """A bare 41 tells a user nothing. It has to say what to change."""
    result = rank(family_state(), listings, limit=20)
    limited = [
        dim
        for rec in result.empfehlungen
        for dim in rec.score.dimensionen
        if dim.begrenzt_durch
    ]
    assert limited, "no composite dimension reported a limiting component"
    for dim in limited:
        assert dim.begrenzt_durch in {c.name for c in dim.komponenten}
        explanation = dim.erklaerung()
        assert "begrenzt durch" in explanation
        assert dim.begrenzt_durch in explanation


def test_the_weakest_component_is_the_one_reported(listings):
    result = rank(family_state(), listings, limit=20)
    for rec in result.empfehlungen:
        for dim in rec.score.dimensionen:
            if dim.komponenten:
                worst = min(dim.komponenten, key=lambda c: c.wert)
                assert dim.begrenzt_durch == worst.name


def test_scores_declare_themselves_relative_to_the_survivor_pool(listings):
    """Percentile scores move when the filter moves. That must be visible."""
    st = family_state()
    survivors, _ = hard_filter(st, listings)
    result = rank(st, listings, limit=5)
    for rec in result.empfehlungen:
        assert rec.score.basis_anzahl == len(survivors)
        assert str(len(survivors)) in rec.score.relativ_hinweis
        assert all(d.relativ for d in rec.score.dimensionen)


def test_the_same_car_scores_differently_against_a_different_pool(listings):
    """Documents the consequence of ranking rather than rating, so it is not a surprise."""
    st = family_state()
    survivors, _ = hard_filter(st, listings)
    target = survivors[0]

    wide = {r.listing.id: r.score.total for r in rank(st, survivors, limit=len(survivors)).empfehlungen}
    narrow_pool = survivors[:5]
    narrow = {r.listing.id: r.score.total for r in rank(st, narrow_pool, limit=5).empfehlungen}

    assert wide[target.id] != narrow[target.id]


# ------------------------------------------------------------------ rental costing


def rental_state(tage: int | None = None) -> InterviewState:
    st = InterviewState()
    st.intent = st.intent.state(Intent.MIETE)
    st.use_case_tags = st.use_case_tags.state([UseCaseTag.UMZUG])
    st.budget = st.budget.state(Budget(max_tagessatz_eur=95))
    st.location = st.location.state(Location(plz="20095", ort="Hamburg"))
    if tage is not None:
        st.mietdauer_tage = st.mietdauer_tage.state(tage)
    return st


def test_a_rental_is_costed_by_the_rental_model_not_the_ownership_model(listings):
    """B-1. The renter was being charged five years of tax they never pay."""
    st = rental_state(3)
    result = rank(st, listings, limit=5, tco_fn=tco_for_state)
    assert result.empfehlungen

    for rec in result.empfehlungen:
        assert rec.listing.listing_type == "miete"
        expected = rental_cost(rec.listing, 3).gesamt_miete_eur
        assert rec.tco_gesamt_eur == expected
        # The five year ownership total for the same car is a different order of
        # magnitude. If these ever coincide, the routing has regressed.
        assert rec.tco_gesamt_eur < 5_000


def test_the_cost_dimension_is_relabelled_for_a_rental(listings):
    st = rental_state(3)
    result = rank(st, listings, limit=3, tco_fn=tco_for_state, lang="de")
    for rec in result.empfehlungen:
        kosten = next(
            d for d in rec.score.dimensionen if d.name is Dimension.GESAMTKOSTEN
        )
        assert kosten.label == "Mietkosten"
        assert "fünf Jahre" not in kosten.begruendung
        assert "3 Tage" in kosten.begruendung


def test_the_cost_dimension_keeps_its_ownership_label_for_a_purchase(listings):
    result = rank(family_state(), listings, limit=3, tco_fn=tco_for_state, lang="de")
    for rec in result.empfehlungen:
        kosten = next(
            d for d in rec.score.dimensionen if d.name is Dimension.GESAMTKOSTEN
        )
        assert kosten.label == "Gesamtkosten"
        assert "fünf Jahre" in kosten.begruendung


def test_a_longer_stated_rental_raises_the_cost_of_every_candidate(listings):
    short = rank(rental_state(2), listings, limit=5, tco_fn=tco_for_state)
    long = rank(rental_state(9), listings, limit=5, tco_fn=tco_for_state)
    by_id = {r.listing.id: r.tco_gesamt_eur for r in short.empfehlungen}
    for rec in long.empfehlungen:
        if rec.listing.id in by_id:
            assert rec.tco_gesamt_eur > by_id[rec.listing.id]


def test_a_rental_gets_a_default_pickup_radius_the_user_never_asked_for(listings):
    """B-2. Distance was a three percent soft weight and a 404 km van won."""
    st = rental_state(3)
    survivors, report = hard_filter(st, listings)
    assert report.angenommener_radius_km == STANDARD_MIET_RADIUS_KM
    for listing in survivors:
        d = distance_km("20095", listing.standort_plz)
        assert d is None or d <= STANDARD_MIET_RADIUS_KM


def test_the_assumed_radius_is_stated_rather_than_applied_silently(listings):
    st = rental_state(3)
    _, report = hard_filter(st, listings)
    assert "entfernung" in report.ausgeschlossen
    assert "100 km angenommen" in report.erklaerung("de")
    assert "assumed, not stated" in report.erklaerung("en")


def test_a_stated_radius_beats_the_default(listings):
    st = rental_state(3)
    st.location = st.location.state(
        Location(plz="20095", ort="Hamburg", max_entfernung_km=400)
    )
    survivors, report = hard_filter(st, listings)
    assert report.angenommener_radius_km is None
    assert "angenommen" not in report.erklaerung("de")
    assert len(survivors) > len(hard_filter(rental_state(3), listings)[0])


def test_a_purchase_keeps_distance_as_a_soft_weight(listings):
    """The default is a rental rule. Buyers do travel for the right car."""
    _, report = hard_filter(family_state(), listings)
    assert report.angenommener_radius_km is None
    assert "entfernung" not in report.ausgeschlossen


# ------------------------------------------------------------------ availability


def test_a_rental_unavailable_on_the_target_date_is_excluded(listings):
    """The brief names the target date as an interview field, so it has to do work."""
    st = rental_state(3)
    st.location = st.location.state(Location(plz="20095", ort="Hamburg", max_entfernung_km=2000))
    st.target_date = st.target_date.state(date(2026, 11, 15))

    survivors, report = hard_filter(st, listings)
    assert report.ausgeschlossen.get("verfuegbarkeit", 0) > 0, (
        "no listing was excluded on availability, so the constraint is inert"
    )
    for listing in survivors:
        assert listing.verfuegbar_bis is None or (
            date.fromisoformat(listing.verfuegbar_bis) >= date(2026, 11, 15)
        )


def test_a_date_before_every_window_leaves_no_rental(listings):
    st = rental_state(3)
    st.target_date = st.target_date.state(date(2026, 1, 1))
    survivors, report = hard_filter(st, listings)
    assert survivors == []
    assert report.ausgeschlossen["verfuegbarkeit"] > 0


def test_flexibility_widens_the_window_on_both_sides(listings):
    """Someone who can shift by a few days should see the offers that allows."""
    st = rental_state(3)
    st.location = st.location.state(Location(plz="20095", ort="Hamburg", max_entfernung_km=2000))
    st.target_date = st.target_date.state(date(2026, 7, 30))  # two days before every window

    strict, _ = hard_filter(st, listings)
    st.date_flexibility_days = st.date_flexibility_days.state(3)
    lenient, _ = hard_filter(st, listings)

    assert len(lenient) > len(strict)


def test_a_purchase_is_never_excluded_on_availability(listings):
    """A car for sale is available when it is sold. Only rentals hold a window."""
    st = family_state()
    st.target_date = st.target_date.state(date(2027, 12, 1))
    _, report = hard_filter(st, listings)
    assert "verfuegbarkeit" not in report.ausgeschlossen


def test_no_target_date_excludes_nothing(listings):
    """An unasked question must not silently narrow the field."""
    ohne = hard_filter(rental_state(3), listings)[1]
    assert "verfuegbarkeit" not in ohne.ausgeschlossen


def test_availability_is_reported_in_the_fixed_constraint_order(listings):
    assert "verfuegbarkeit" in CONSTRAINT_ORDER
    st = rental_state(3)
    st.target_date = st.target_date.state(date(2026, 12, 20))
    _, report = hard_filter(st, listings)
    reihenfolge = [k for k in CONSTRAINT_ORDER if k in report.ausgeschlossen]
    assert list(report.ausgeschlossen) == reihenfolge, "drop counts left the fixed order"


@pytest.mark.parametrize("lang", ["de", "en"])
def test_the_availability_constraint_has_a_label_in_both_languages(lang):
    from agent.tools.ranking import constraint_label

    label = constraint_label("verfuegbarkeit", lang)
    assert label and label != "c.verfuegbarkeit" and "_" not in label


def test_an_unstated_rental_duration_falls_back_to_the_standing_assumption(listings):
    """No duration in state must not mean no cost. It means the documented default."""
    result = rank(rental_state(), listings, limit=3, tco_fn=tco_for_state)
    for rec in result.empfehlungen:
        assert rec.tco_gesamt_eur == (
            rental_cost(rec.listing, STANDARD_MIETDAUER_TAGE).gesamt_miete_eur
        )
