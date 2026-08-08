"""The language toggle.

The contract is narrow and worth pinning: everything a reader reads is translated,
and nothing that names a real thing ever is.
"""

from __future__ import annotations

import pytest

from agent import i18n
from agent.listing import KATEGORIEN, load_listings
from agent.state import Dimension
from agent.surfaces.katalog import build_messages
from agent.tools.ranking import constraint_label, rank
from agent.tools.tco import cost_of_ownership
from mcpapps.formular.server import render_for as render_formular
from mcpapps.kasse.server import build_order
from mcpapps.kasse.server import render_for as render_kasse
from tests.test_ranking import family_state


# ------------------------------------------------------------------ basics


def test_german_is_the_default():
    assert i18n.DEFAULT_LANG == "de"


@pytest.mark.parametrize(
    "given,expected",
    [("de", "de"), ("en", "en"), ("EN", "en"), ("de-DE", "de"), ("fr", "de"),
     ("", "de"), (None, "de")],
)
def test_unknown_languages_fall_back_to_german(given, expected):
    assert i18n.normalise(given) == expected


def test_numbers_follow_the_language():
    assert i18n.fmt_int(52_920, "de") == "52.920"
    assert i18n.fmt_int(52_920, "en") == "52,920"
    assert i18n.fmt_dec(21_490.0, "de", 2) == "21.490,00"
    assert i18n.fmt_dec(21_490.0, "en", 2) == "21,490.00"


# ------------------------------------------------------------------ vocabulary


def test_every_category_has_an_english_gloss():
    missing = [c for c in KATEGORIEN if c not in i18n.KATEGORIE_GLOSS]
    assert not missing, f"categories without a gloss: {missing}"


def test_segment_names_are_glossed_not_replaced():
    """A reader should still be able to match the term against a real listing."""
    assert i18n.kategorie("Kompaktklasse", "de") == "Kompaktklasse"
    english = i18n.kategorie("Kompaktklasse", "en")
    assert english.startswith("Kompaktklasse")
    assert "compact" in english


def test_fuel_and_transmission_translate():
    assert i18n.kraftstoff("Benzin", "en") == "petrol"
    assert i18n.kraftstoff("Benzin", "de") == "Benzin"
    assert i18n.getriebe("Schaltgetriebe", "en") == "manual"


def test_every_dimension_and_constraint_has_both_languages():
    for dim in Dimension:
        for lang in i18n.LANGS:
            value = i18n.t(f"dim.{dim.value}", lang)
            assert value and value != f"dim.{dim.value}"
    from agent.tools.ranking import CONSTRAINT_ORDER

    for key in CONSTRAINT_ORDER:
        for lang in i18n.LANGS:
            assert constraint_label(key, lang) != f"c.{key}"


def test_every_key_carries_both_languages():
    """A key with a language missing would render as the raw key in the interface.

    Not asserting that a value differs from its key: several German values legitimately
    equal it, "ausgeschlossen" among them.
    """
    incomplete = {
        key: sorted(set(i18n.LANGS) - set(entry))
        for key, entry in i18n.STRINGS.items()
        if set(i18n.LANGS) - set(entry)
    }
    assert not incomplete, f"keys missing a language: {incomplete}"

    empty = [
        f"{key}/{lang}"
        for key, entry in i18n.STRINGS.items()
        for lang in i18n.LANGS
        if not entry[lang].strip()
    ]
    assert not empty, f"empty translations: {empty}"


def test_an_unknown_key_returns_itself_rather_than_crashing():
    assert i18n.t("kein.solcher.schluessel", "en") == "kein.solcher.schluessel"


# ------------------------------------------------------------------ ranking


def test_ranking_explanations_translate():
    listings = load_listings()
    st = family_state()
    de = rank(st, listings, limit=1, lang="de")
    en = rank(st, listings, limit=1, lang="en")

    assert "Angebote geprüft" in de.report.erklaerung("de")
    assert "listings checked" in en.report.erklaerung("en")
    assert de.empfehlungen[0].score.dimensionen[0].label == "Preisspielraum"
    assert en.empfehlungen[0].score.dimensionen[0].label == "Price headroom"


def test_the_same_listing_is_chosen_in_both_languages():
    """Language changes wording, never the ranking. Scores must be identical."""
    listings = load_listings()
    de = rank(family_state(), listings, limit=6, lang="de")
    en = rank(family_state(), listings, limit=6, lang="en")
    assert [r.listing.id for r in de.empfehlungen] == [r.listing.id for r in en.empfehlungen]
    assert [r.score.total for r in de.empfehlungen] == [r.score.total for r in en.empfehlungen]


def test_relativity_notice_translates():
    listings = load_listings()
    r = rank(family_state(), listings, limit=1)
    assert "Platzierung" in r.empfehlungen[0].score.relativ_hinweis_lang("de")
    assert "placing" in r.empfehlungen[0].score.relativ_hinweis_lang("en")


# ------------------------------------------------------------------ proper nouns


def test_proper_nouns_are_never_translated():
    """Brands, models, dealers and places must read identically in both languages."""
    listings = load_listings()
    st = family_state()
    de = build_messages(rank(st, listings, limit=4, lang="de"), lang="de")
    en = build_messages(rank(st, listings, limit=4, lang="en"), lang="en")

    def cards(msgs):
        comps = msgs[1]["updateComponents"]["components"]
        return {c["listingId"]: c for c in comps if c["component"] == "FahrzeugKarte"}

    de_cards, en_cards = cards(de), cards(en)
    assert de_cards.keys() == en_cards.keys()
    for listing_id, card in de_cards.items():
        other = en_cards[listing_id]
        assert card["bezeichnung"] == other["bezeichnung"], "model name was translated"
        assert card["haendler"] == other["haendler"], "dealer name was translated"


def test_place_names_survive_in_the_distance_justification():
    listings = load_listings()
    en = rank(family_state(), listings, limit=1, lang="en")
    distance = [
        d for d in en.empfehlungen[0].score.dimensionen if d.name is Dimension.ENTFERNUNG
    ][0]
    # The sentence is English, the place inside it is not.
    assert " to " in distance.begruendung
    assert en.empfehlungen[0].listing.standort_ort in distance.begruendung


# ------------------------------------------------------------------ cost


def test_cost_of_ownership_line_items_translate():
    listing = [l for l in load_listings() if l.listing_type == "kauf"][0]
    de = cost_of_ownership(listing, 15_000, None, "de")
    en = cost_of_ownership(listing, 15_000, None, "en")
    assert [n for n, _ in de.posten("de")][0] == "Kfz-Steuer"
    assert [n for n, _ in en.posten("en")][0] == "Vehicle tax"
    assert de.gesamt_5j_eur == en.gesamt_5j_eur, "language changed a number"


def test_the_estimate_disclaimer_translates():
    listing = [l for l in load_listings() if l.listing_type == "kauf"][0]
    assert "Schätzungen" in cost_of_ownership(listing, 15_000, None, "de").schaetzung_hinweis
    assert "estimates" in cost_of_ownership(listing, 15_000, None, "en").schaetzung_hinweis


# ------------------------------------------------------------------ surfaces


def test_form_translates_both_flows():
    for intent, de_word, en_word in [
        ("kauf", "Kaufanfrage", "Purchase enquiry"),
        ("miete", "Mietanfrage", "Rental enquiry"),
    ]:
        assert de_word in render_formular(intent, "X", "FB-1", "de")
        assert en_word in render_formular(intent, "X", "FB-1", "en")


def test_checkout_translates_the_invoice():
    de = render_kasse(build_order("FB-1", "X", "kauf", 2_149_000, lang="de"), "de")
    en = render_kasse(build_order("FB-1", "X", "kauf", 2_149_000, lang="en"), "en")
    assert "19 % MwSt." in de and "Nettobetrag" in de
    assert "19 % VAT" in en and "Net amount" in en


def test_the_simulation_token_never_translates():
    """M-5. The token must read identically in every language, everywhere."""
    for lang in i18n.LANGS:
        html = render_kasse(build_order("FB-1", "X", "kauf", 100_000, lang=lang), lang)
        assert "SIMULATION" in html
        assert "DE00 SIMU LATI ON00 0000 00" in html


def test_no_card_field_appears_in_either_language():
    for lang in i18n.LANGS:
        html = render_kasse(build_order("FB-1", "X", "kauf", 100_000, lang=lang), lang).lower()
        for needle in ("kartennummer", "cardnumber", "cvv", "<input"):
            assert needle not in html


def test_the_page_language_attribute_follows_the_choice():
    for lang in i18n.LANGS:
        assert f'<html lang="{lang}"' in render_formular("kauf", "X", "FB-1", lang)
        assert f'<html lang="{lang}"' in render_kasse(build_order("FB-1", "X", "kauf", 1, lang=lang), lang)


def test_the_checkout_button_reads_naturally_in_both_languages():
    """German puts the verb last, so a concatenation cannot serve both."""
    de = render_kasse(build_order("FB-1", "X", "kauf", 1, lang="de"), "de")
    en = render_kasse(build_order("FB-1", "X", "kauf", 1, lang="en"), "en")
    assert "Kaufvertrag simulieren" in de
    assert "Simulate purchase contract" in en
