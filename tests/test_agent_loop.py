"""The agent loop, tested without calling a model.

Everything here exercises the parts that must hold regardless of what the model says:
the guardrail is present in the prompt, the tools write provenance correctly, sessions
do not leak into each other, and the ranking tool refuses rather than inventing when
it has nothing to work with.
"""

from __future__ import annotations

import pytest

from agent.prompts.system import system_prompt
from agent.state import Intent, Provenance
from agent.store import CURRENT_SESSION, STORE, InMemorySessionStore
from agent.tools.interview import (
    AGENT_TOOLS,
    empfehlungen_erstellen,
    interview_merken,
    interview_stand,
)


@pytest.fixture(autouse=True)
def _clean_session():
    for sid in ("t1", "t2"):
        STORE.clear(sid)
    token = CURRENT_SESSION.set("t1")
    yield
    CURRENT_SESSION.reset(token)
    for sid in ("t1", "t2"):
        STORE.clear(sid)


# ------------------------------------------------------------------ guardrail


@pytest.mark.parametrize("lang", ["de", "en"])
def test_the_prompt_forbids_inventing_facts(lang):
    prompt = system_prompt(lang)
    needles = {
        "de": ["NIEMALS", "Werkzeugausgabe", "Rechne nicht selbst", "Erfinde keine"],
        "en": ["NEVER", "tool result", "Do not calculate", "Never invent"],
    }[lang]
    for needle in needles:
        assert needle in prompt, f"guardrail phrase missing: {needle!r}"


@pytest.mark.parametrize("lang", ["de", "en"])
def test_the_prompt_says_narrate_not_author(lang):
    prompt = system_prompt(lang)
    assert ("Du erzählst die Rangfolge" in prompt) or (
        "You narrate the ranking" in prompt
    )


@pytest.mark.parametrize("lang", ["de", "en"])
def test_the_prompt_prefers_admitting_ignorance_to_guessing(lang):
    prompt = system_prompt(lang)
    assert ("Diese Angabe habe ich nicht" in prompt) or ("I do not have that" in prompt)


@pytest.mark.parametrize("lang", ["de", "en"])
def test_the_prompt_carries_the_interview_policy(lang):
    prompt = system_prompt(lang)
    assert ("höchstens zwei" in prompt) or ("at most two" in prompt)
    assert ("interview_stand" in prompt)


def test_three_tools_are_registered():
    assert {t.name for t in AGENT_TOOLS} == {
        "interview_merken",
        "interview_stand",
        "empfehlungen_erstellen",
    }


# ------------------------------------------------------------------ provenance


def test_stated_and_inferred_are_recorded_differently():
    interview_merken.invoke({"herkunft": "gesagt", "intent": "kauf"})
    interview_merken.invoke(
        {"herkunft": "abgeleitet", "min_sitzplaetze": 5, "quelle": "Familie erwähnt"}
    )
    state = STORE.load("t1")
    assert state.intent.provenance is Provenance.STATED
    assert state.constraints_hard.provenance is Provenance.INFERRED
    assert state.constraints_hard.needs_confirmation


def test_an_inference_cannot_overwrite_something_stated():
    interview_merken.invoke({"herkunft": "gesagt", "max_kaufpreis_eur": 25_000})
    interview_merken.invoke({"herkunft": "abgeleitet", "max_kaufpreis_eur": 9_000})
    state = STORE.load("t1")
    assert state.budget.value.max_kaufpreis_eur == 25_000


def test_an_unknown_intent_is_refused_rather_than_guessed():
    out = interview_merken.invoke({"intent": "leasing"})
    assert "unbekannt" in out
    assert not STORE.load("t1").intent.is_set


def test_free_text_derives_use_case_tags():
    interview_merken.invoke(
        {"use_case_text": "Ich fahre meine zwei Kinder zur Schule und pendle zur Arbeit"}
    )
    tags = {t.value for t in STORE.load("t1").use_case_tags.value or []}
    assert "familie" in tags and "pendeln" in tags


def test_the_status_tool_reports_what_is_known_and_missing():
    interview_merken.invoke({"herkunft": "gesagt", "intent": "kauf"})
    out = interview_stand.invoke({})
    assert "intent" in out and "kauf" in out
    assert "Offen:" in out


def test_the_status_tool_marks_inferences_awaiting_confirmation():
    interview_merken.invoke({"herkunft": "abgeleitet", "min_kofferraum_liter": 400})
    assert "zu bestätigen" in interview_stand.invoke({})


# ------------------------------------------------------------------ sessions


def test_sessions_do_not_leak_into_each_other():
    interview_merken.invoke({"herkunft": "gesagt", "intent": "kauf"})
    token = CURRENT_SESSION.set("t2")
    try:
        assert not STORE.load("t2").intent.is_set
        interview_merken.invoke({"herkunft": "gesagt", "intent": "miete"})
        assert STORE.load("t2").intent.value is Intent.MIETE
    finally:
        CURRENT_SESSION.reset(token)
    assert STORE.load("t1").intent.value is Intent.KAUF


def test_a_fresh_store_starts_empty():
    store = InMemorySessionStore()
    assert not store.load("neu").intent.is_set
    assert store.artifact("neu", "ranking") is None


# ------------------------------------------------------------------ ranking tool


def test_the_ranking_tool_refuses_before_intent_is_known():
    """It must ask rather than pick a default and produce confident nonsense."""
    out = empfehlungen_erstellen.invoke({"anzahl": 3})
    assert "Absicht" in out
    assert STORE.artifact("t1", "ranking") is None


def test_the_ranking_tool_returns_real_listings_and_stores_the_result():
    interview_merken.invoke(
        {"herkunft": "gesagt", "intent": "kauf", "max_kaufpreis_eur": 25_000}
    )
    out = empfehlungen_erstellen.invoke({"anzahl": 3})

    assert "Rangfolge:" in out
    result = STORE.artifact("t1", "ranking")
    assert result is not None and result.empfehlungen

    # Every identifier the model could quote must belong to a real listing.
    for rec in result.empfehlungen:
        assert f"[{rec.listing.id}]" in out
        assert rec.listing.preis_referenz() <= 25_000


def test_an_empty_result_names_the_constraint_instead_of_offering_something_else():
    interview_merken.invoke(
        {"herkunft": "gesagt", "intent": "kauf", "max_kaufpreis_eur": 1}
    )
    out = empfehlungen_erstellen.invoke({"anzahl": 3})
    assert "Kein Angebot" in out
    assert "Erfinde kein Angebot" in out
    assert "Budget" in out


def test_the_tool_output_tells_the_model_to_keep_its_reply_short():
    """The surface carries the detail. Repeating it in prose wastes tokens and risks
    transcription errors."""
    interview_merken.invoke(
        {"herkunft": "gesagt", "intent": "kauf", "max_kaufpreis_eur": 25_000}
    )
    out = empfehlungen_erstellen.invoke({"anzahl": 3})
    assert "angezeigt" in out


def test_the_ranking_tool_caps_the_result_size():
    interview_merken.invoke(
        {"herkunft": "gesagt", "intent": "kauf", "max_kaufpreis_eur": 40_000}
    )
    empfehlungen_erstellen.invoke({"anzahl": 99})
    assert len(STORE.artifact("t1", "ranking").empfehlungen) <= 8


def test_katalog_endpoint_preserves_active_session_state():
    from agent.server import WeightRequest, katalog

    # Set up an active rental session in t1
    interview_merken.invoke(
        {"herkunft": "gesagt", "intent": "miete", "max_tagessatz_eur": 95}
    )
    interview_merken.invoke({"herkunft": "gesagt", "ort": "Hamburg"})

    # Re-rank via katalog endpoint using session_id
    res = katalog(
        WeightRequest(session_id="t1", gewichte={"gesamtkosten": 1.0}, lang="de")
    )

    # Verify interview payload maintains rental & Hamburg state (not Munich purchase persona)
    interview_payload = res["interview"]
    keys = {r["slot"]: r["wert"] for r in interview_payload}
    assert keys.get("intent") in ("miete", "mieten")
    assert "Hamburg" in str(keys.get("location"))



