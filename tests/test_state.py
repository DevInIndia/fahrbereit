"""Interview state, provenance, and the invalidation asymmetry."""

from __future__ import annotations

import pytest

from agent.state import (
    BASE_WEIGHTS,
    Budget,
    Dimension,
    HardConstraints,
    Intent,
    InterviewState,
    Provenance,
    Slot,
    UseCaseTag,
    tags_from_text,
)


# ------------------------------------------------------------------ provenance


def test_a_stated_value_is_confirmed_immediately():
    s = Slot[int]().state(25000, source="user said 25000")
    assert s.value == 25000
    assert s.provenance is Provenance.STATED
    assert s.confirmed
    assert not s.needs_confirmation


def test_an_inference_must_be_confirmed_before_it_is_trusted():
    s = Slot[int]().infer(15000, confidence=0.6)
    assert s.provenance is Provenance.INFERRED
    assert not s.confirmed
    assert s.needs_confirmation
    assert s.confirm().confirmed


def test_inference_never_overwrites_what_the_user_actually_said():
    """The rule that stops the agent talking over the user."""
    stated = Slot[int]().state(25000)
    still = stated.infer(9999)
    assert still.value == 25000
    assert still.provenance is Provenance.STATED


def test_unconfirmed_inferences_are_listed_for_the_progress_surface():
    st = InterviewState()
    st.intent = st.intent.state(Intent.KAUF)
    st.use_case_tags = st.use_case_tags.infer([UseCaseTag.FAMILIE])
    pending = st.unconfirmed_inferences()
    assert "use_case_tags" in pending
    assert "intent" not in pending


# ------------------------------------------------------------------ no re-ask


def test_knows_reports_what_must_not_be_asked_again():
    st = InterviewState()
    assert not st.knows("budget")
    st.budget = st.budget.state(Budget(max_kaufpreis_eur=25000))
    assert st.knows("budget")
    assert "budget" not in st.missing_slots()


# ------------------------------------------------------------------ revision


def test_budget_change_discards_the_ranking_but_keeps_the_interview():
    st = InterviewState()
    st.intent = st.intent.state(Intent.KAUF)
    st.use_case_text = st.use_case_text.state("Zwei Kinder, Schulweg")
    st.budget = st.budget.state(Budget(max_kaufpreis_eur=25000))

    killed = st.revise("budget", Budget(max_kaufpreis_eur=18000))

    assert "ranking" in killed and "filter_report" in killed
    # The interview survives. This is the difference between a state machine and a form.
    assert st.intent.value is Intent.KAUF
    assert st.use_case_text.value == "Zwei Kinder, Schulweg"
    assert st.budget.value.max_kaufpreis_eur == 18000


def test_weight_change_does_not_rerun_the_hard_filter():
    """Re-ranking in place has to be cheap, or the weight control cannot feel live."""
    st = InterviewState()
    killed = st.revise("preferences_soft", {Dimension.GESAMTKOSTEN.value: 0.9})
    assert killed == ["ranking"]
    assert "filter_report" not in killed


def test_annual_mileage_change_invalidates_cost_of_ownership():
    st = InterviewState()
    killed = st.revise("jahresfahrleistung_km", 30000)
    assert "tco" in killed and "ranking" in killed
    assert "filter_report" not in killed


def test_intent_change_invalidates_everything_downstream():
    st = InterviewState()
    killed = st.revise("intent", Intent.MIETE)
    for artifact in ("filter_report", "ranking", "selection", "booking", "order"):
        assert artifact in killed


def test_free_text_invalidates_nothing_computed():
    st = InterviewState()
    assert st.revise("use_case_text", "neue Beschreibung") == []


def test_revising_an_unknown_slot_names_the_valid_ones():
    st = InterviewState()
    with pytest.raises(KeyError) as excinfo:
        st.revise("lieblingsfarbe", "blau")
    assert "budget" in str(excinfo.value)


def test_revision_marks_the_slot_as_stated():
    st = InterviewState()
    st.jahresfahrleistung_km = st.jahresfahrleistung_km.infer(12000)
    st.revise("jahresfahrleistung_km", 30000)
    assert st.jahresfahrleistung_km.provenance is Provenance.STATED


# ------------------------------------------------------------------ weights


def test_weights_always_sum_to_one():
    st = InterviewState()
    assert sum(st.weights().values()) == pytest.approx(1.0)


def test_use_case_tags_shift_the_emphasis():
    plain = InterviewState().weights()

    commuter = InterviewState()
    commuter.use_case_tags = commuter.use_case_tags.state([UseCaseTag.PENDELN])
    assert commuter.weights()[Dimension.GESAMTKOSTEN] > plain[Dimension.GESAMTKOSTEN]

    family = InterviewState()
    family.use_case_tags = family.use_case_tags.state([UseCaseTag.FAMILIE])
    assert family.weights()[Dimension.EINSATZZWECK] > plain[Dimension.EINSATZZWECK]


def test_explicit_weights_override_the_derivation():
    st = InterviewState()
    st.use_case_tags = st.use_case_tags.state([UseCaseTag.FAMILIE])
    st.preferences_soft = st.preferences_soft.state({Dimension.GESAMTKOSTEN.value: 1.0})
    w = st.weights()
    assert w[Dimension.GESAMTKOSTEN] == pytest.approx(1.0)
    assert w[Dimension.EINSATZZWECK] == pytest.approx(0.0)


def test_every_dimension_is_present_even_at_zero():
    st = InterviewState()
    st.preferences_soft = st.preferences_soft.state({Dimension.ZUSTAND.value: 1.0})
    assert set(st.weights()) == set(Dimension)


# ------------------------------------------------------------------ inference


def test_tags_inferred_from_the_users_own_words():
    tags = tags_from_text("Ich fahre meine zwei Kinder zur Schule und pendle zur Arbeit")
    assert UseCaseTag.FAMILIE in tags
    assert UseCaseTag.PENDELN in tags


def test_inference_is_conservative_rather_than_eager():
    assert tags_from_text("Ich brauche ein Auto") == []


def test_inference_is_deterministic():
    text = "Umzug und Wochenende in der Stadt"
    assert tags_from_text(text) == tags_from_text(text)


# ------------------------------------------------------------------ defaults


def test_no_category_preference_means_every_category_is_open():
    from agent.listing import KATEGORIEN

    assert InterviewState().effective_categories() == KATEGORIEN


def test_hard_constraints_default_to_permissive():
    c = HardConstraints()
    assert c.getriebe is None
    assert not c.unfallfrei_erforderlich
