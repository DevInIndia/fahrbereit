"""The ranking pipeline. Determinism, constraint satisfaction, and arithmetic."""

from __future__ import annotations

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
from agent.tools.ranking import CONSTRAINT_ORDER, hard_filter, rank, score_listings


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
