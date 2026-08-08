"""The A2UI surfaces. Mandatory requirement M-4.

Two things are being defended here and they are different.

The first is the wire format. The renderer is A2UI v0.9 and it accepts a v0.8 message
without complaint and draws nothing at all. That failure mode is the reason this file
exists: a silent blank surface looks identical to a surface that was never sent, so
the format is asserted rather than assumed. v0.8 wrapped values as {"literal": ...}
and used beginRendering and surfaceUpdate; none of that may reappear.

The second is that the interface computes nothing. Every number on a card has to be
the number the ranking engine produced, not a rounded, reformatted or recalculated
version of it. These tests compare the emitted props against the RankingResult field
by field, so a helpful little calculation added to the surface layer fails here.
"""

from __future__ import annotations

from datetime import date

import pytest

from agent.listing import load_listings
from agent.state import (
    Budget,
    HardConstraints,
    Intent,
    InterviewState,
    Location,
    Phase,
    UseCaseTag,
)
from agent.surfaces import fortschritt
from agent.surfaces.katalog import (
    CATALOG_ID,
    SURFACE_ID,
    build_messages,
    build_weight_update,
)
from agent.tools.ranking import rank
from agent.tools.tco import tco_for_state

# v0.8 spellings. Any of these in a payload means the renderer will draw nothing.
VERALTETE_SCHLUESSEL = ("beginRendering", "surfaceUpdate", "literal")


@pytest.fixture
def listings():
    return load_listings()


def familie() -> InterviewState:
    st = InterviewState(session_id="a2ui-familie")
    st.intent = st.intent.state(Intent.KAUF)
    st.budget = st.budget.state(Budget(max_kaufpreis_eur=25_000))
    st.use_case_tags = st.use_case_tags.state([UseCaseTag.FAMILIE])
    st.constraints_hard = st.constraints_hard.state(
        HardConstraints(min_sitzplaetze=5, unfallfrei_erforderlich=True)
    )
    st.location = st.location.state(Location(plz="80339", ort="München"))
    st.target_date = st.target_date.state(date(2026, 9, 1))
    return st


def miete() -> InterviewState:
    st = InterviewState(session_id="a2ui-miete")
    st.intent = st.intent.state(Intent.MIETE)
    st.budget = st.budget.state(Budget(max_tagessatz_eur=95))
    st.mietdauer_tage = st.mietdauer_tage.state(3)
    st.location = st.location.state(Location(plz="20095", ort="Hamburg"))
    return st


def result_for(state, listings, limit: int = 5, lang: str = "de"):
    return rank(state, listings, limit=limit, tco_fn=tco_for_state, lang=lang)


def components_of(messages: list[dict]) -> dict[str, dict]:
    """Every component in a message list, keyed by id."""
    out: dict[str, dict] = {}
    for message in messages:
        payload = message.get("updateComponents")
        if payload:
            for component in payload["components"]:
                out[component["id"]] = component
    return out


# ------------------------------------------------------------------ wire format


@pytest.mark.parametrize("lang", ["de", "en"])
def test_the_catalogue_speaks_v0_9(listings, lang):
    messages = build_messages(result_for(familie(), listings), lang=lang)
    assert messages, "no messages emitted"
    for message in messages:
        assert message["version"] == "v0.9", f"wrong wire version in {message}"


def test_the_catalogue_opens_with_create_surface_then_updates(listings):
    messages = build_messages(result_for(familie(), listings))
    assert "createSurface" in messages[0]
    assert messages[0]["createSurface"] == {
        "surfaceId": SURFACE_ID,
        "catalogId": CATALOG_ID,
    }
    assert all("updateComponents" in m for m in messages[1:])


def test_no_v0_8_spelling_survives_anywhere(listings):
    """The v0.8 renderer failure was silent, so this is asserted, not assumed."""
    import json

    for payload in (
        build_messages(result_for(familie(), listings)),
        build_weight_update(result_for(familie(), listings)),
        fortschritt.initial_messages(familie()),
        [fortschritt.phase_message(Phase.SUCHE)],
    ):
        blob = json.dumps(payload)
        for veraltet in VERALTETE_SCHLUESSEL:
            assert veraltet not in blob, f"{veraltet} is v0.8 and renders nothing"


def test_component_props_are_flat_not_nested(listings):
    """v0.9 puts props on the component object. Nesting them draws nothing."""
    for component in components_of(build_messages(result_for(familie(), listings))).values():
        assert "component" in component and "id" in component
        assert "props" not in component, "props must be flat on the component in v0.9"


def test_every_surface_mounts_a_component_called_root(listings):
    """The renderer mounts the node with id root and nothing else."""
    for messages in (
        build_messages(result_for(familie(), listings)),
        fortschritt.initial_messages(familie()),
    ):
        assert "root" in components_of(messages)


def test_every_child_reference_resolves_to_a_real_component(listings):
    """A dangling id in `kinder` renders as a hole, silently."""
    for messages in (
        build_messages(result_for(familie(), listings)),
        fortschritt.initial_messages(familie()),
    ):
        components = components_of(messages)
        for component in components.values():
            for child in component.get("kinder", []):
                assert child in components, f"{child} is referenced but never defined"


# ------------------------------------------------------------------ the catalogue


def test_the_catalogue_renders_one_card_per_recommendation(listings):
    result = result_for(familie(), listings, limit=4)
    components = components_of(build_messages(result))
    karten = [c for c in components.values() if c["component"] == "FahrzeugKarte"]
    assert len(karten) == len(result.empfehlungen) == 4
    assert [k["listingId"] for k in karten] == [r.listing.id for r in result.empfehlungen]


def test_the_catalogue_carries_the_engine_numbers_unchanged(listings):
    """The interface computes nothing. Every figure must match the engine exactly."""
    result = result_for(familie(), listings, limit=3)
    components = components_of(build_messages(result))

    for rec in result.empfehlungen:
        karte = components[f"karte-{rec.listing.id}"]
        assert karte["rang"] == rec.rang
        assert karte["punkte"] == rec.score.total
        assert karte["basisAnzahl"] == rec.score.basis_anzahl
        assert karte["tcoGesamt"] == (rec.tco_gesamt_eur or 0)
        assert karte["istMiete"] is (rec.listing.listing_type == "miete")

        for emitted, dimension in zip(karte["dimensionen"], rec.score.dimensionen):
            assert emitted["wert"] == dimension.rohwert
            assert emitted["gewicht"] == dimension.gewicht
            assert emitted["beitrag"] == dimension.beitrag
            assert emitted["label"] == dimension.label


def test_the_filter_report_matches_the_engine(listings):
    result = result_for(familie(), listings)
    bericht = components_of(build_messages(result))["filter"]
    assert bericht["gesamt"] == result.report.gesamt
    assert bericht["uebrig"] == result.report.uebrig
    assert len(bericht["ausgeschlossen"]) == len(result.report.ausgeschlossen)
    assert sum(row["anzahl"] for row in bericht["ausgeschlossen"]) == (
        result.report.ausgeschlossen_gesamt
    )


def test_the_weights_panel_sums_to_one(listings):
    result = result_for(familie(), listings)
    panel = components_of(build_messages(result))["gewichte"]
    assert sum(g["anteil"] for g in panel["gewichte"]) == pytest.approx(1.0, abs=1e-3)
    assert [g["anteil"] for g in panel["gewichte"]] == sorted(
        (g["anteil"] for g in panel["gewichte"]), reverse=True
    ), "weights are emitted largest first so the panel reads as a ranking"


def test_a_rental_card_is_marked_as_one(listings):
    result = result_for(miete(), listings, limit=3)
    assert result.empfehlungen, "the rental fixture produced nothing to render"
    for karte in components_of(build_messages(result)).values():
        if karte["component"] == "FahrzeugKarte":
            assert karte["istMiete"] is True
            assert "/Tag" in karte["preis"] or "/day" in karte["preis"]


@pytest.mark.parametrize("lang", ["de", "en"])
def test_the_catalogue_carries_no_raw_identifier_in_a_label(listings, lang):
    components = components_of(build_messages(result_for(familie(), listings), lang=lang))
    for karte in components.values():
        if karte["component"] != "FahrzeugKarte":
            continue
        for dimension in karte["dimensionen"]:
            assert "_" not in dimension["label"], (
                f"{dimension['label']} looks like an internal key, not a label"
            )


# ------------------------------------------------------------------ incremental path


def test_a_weight_change_updates_in_place_without_rebuilding(listings):
    """FR-034. Rebuilding the surface would collapse every expanded card."""
    messages = build_weight_update(result_for(familie(), listings))
    assert len(messages) == 1
    assert "createSurface" not in messages[0], "a weight change must not rebuild"
    assert messages[0]["version"] == "v0.9"

    payload = messages[0]["updateComponents"]
    assert payload["surfaceId"] == SURFACE_ID
    assert [c["id"] for c in payload["components"]] == ["gewichte"], (
        "only the weights panel may be touched"
    )


def test_a_weight_change_actually_changes_the_emitted_weights(listings):
    state = familie()
    before = components_of(build_weight_update(result_for(state, listings)))["gewichte"]

    state.preferences_soft = state.preferences_soft.state({"gesamtkosten": 1.0})
    after = components_of(build_weight_update(result_for(state, listings)))["gewichte"]

    assert before["gewichte"] != after["gewichte"]
    top = max(after["gewichte"], key=lambda g: g["anteil"])
    assert top["anteil"] == pytest.approx(1.0, abs=1e-3)


# ------------------------------------------------------------------ progress surface


def test_the_progress_surface_lays_out_its_panels_once(listings):
    messages = fortschritt.initial_messages(familie())
    assert "createSurface" in messages[0]
    assert messages[0]["createSurface"]["surfaceId"] == fortschritt.SURFACE_ID

    components = components_of(messages)
    assert {"PhasenAnzeige", "SlotCheckliste", "SuchStatus", "WerkzeugStrom"} <= {
        c["component"] for c in components.values()
    }


def test_the_progress_surface_covers_what_the_brief_asks_for(listings):
    """Interview state, search status and reasoning steps, each as its own panel."""
    components = components_of(fortschritt.initial_messages(familie()))

    slots = components["slots"]
    assert slots["gesamt"] == len(slots["zeilen"]) > 0
    assert slots["gefuellt"] > 0, "the interview state panel shows nothing"

    assert components["suche"]["component"] == "SuchStatus"
    assert components["strom"]["component"] == "WerkzeugStrom"


def test_exactly_one_phase_is_active_at_a_time():
    for phase in fortschritt.PHASEN:
        message = fortschritt.phase_message(phase)
        phasen = message["updateComponents"]["components"][0]["phasen"]
        assert sum(1 for p in phasen if p["aktiv"]) == 1
        assert [p for p in phasen if p["aktiv"]][0]["name"] == phase.value


def test_each_progress_update_carries_only_the_component_that_changed():
    """The point of the surface is that it changes while the user waits."""
    state = familie()
    fuer = {
        "phase": fortschritt.phase_message(Phase.SUCHE),
        "slots": fortschritt.slots_message(state),
        "suche": fortschritt.suche_message(None),
        "strom": fortschritt.strom_message([]),
    }
    for erwartete_id, message in fuer.items():
        assert "createSurface" not in message
        components = message["updateComponents"]["components"]
        assert [c["id"] for c in components] == [erwartete_id]


def test_the_search_panel_reports_the_real_drop_counts(listings):
    result = result_for(familie(), listings)
    message = fortschritt.suche_message(result.report, "de")
    panel = message["updateComponents"]["components"][0]
    assert panel["gesamt"] == result.report.gesamt
    assert panel["uebrig"] == result.report.uebrig
    assert sum(r["anzahl"] for r in panel["ausgeschlossen"]) == (
        result.report.ausgeschlossen_gesamt
    )


def test_the_slot_checklist_marks_an_inference_for_confirmation():
    state = familie()
    state.jahresfahrleistung_km = state.jahresfahrleistung_km.infer(15_000)
    zeilen = components_of([fortschritt.slots_message(state)])["slots"]["zeilen"]
    assert any(z["zuBestaetigen"] for z in zeilen), "no inference marked for confirmation"
    assert all(
        not z["zuBestaetigen"] for z in zeilen if z["herkunft"] == "stated"
    ), "a stated value must never be marked for confirmation"


@pytest.mark.parametrize("lang", ["de", "en"])
def test_the_progress_surface_translates(lang):
    components = components_of(fortschritt.initial_messages(familie(), lang))
    labels = [p["label"] for p in components["phase"]["phasen"]]
    assert labels == [fortschritt.PHASE_LABEL[p][lang] for p in fortschritt.PHASEN]
    assert components["strom"]["titel"] == (
        "Werkzeugaufrufe" if lang == "de" else "Tool calls"
    )
