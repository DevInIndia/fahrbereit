"""Dataset invariants. These are graded requirements, so they are asserted, not assumed."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pytest

from agent.listing import KATEGORIEN, Listing, load_listings
from data.generate import OUTPUT, SEED, generate
from data.vocab import MODELLE, VERBOTENE_NAMEN

MIN_LISTINGS = 250
MIN_BRANDS_PER_CATEGORY = 10


@pytest.fixture(scope="module")
def listings() -> tuple[Listing, ...]:
    return load_listings()


@pytest.fixture(scope="module")
def raw() -> list[dict]:
    return json.loads(OUTPUT.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ scale, M-6


def test_at_least_250_listings(listings):
    assert len(listings) >= MIN_LISTINGS


def test_exactly_ten_categories(listings):
    found = {l.category for l in listings}
    assert len(found) == 10
    assert found == set(KATEGORIEN)


def test_at_least_ten_brands_in_every_category(listings):
    per_category = defaultdict(set)
    for l in listings:
        per_category[l.category].add(l.brand)
    short = {c: sorted(b) for c, b in per_category.items() if len(b) < MIN_BRANDS_PER_CATEGORY}
    assert not short, f"categories below {MIN_BRANDS_PER_CATEGORY} brands: {short}"


def test_both_listing_types_exist_in_every_category(listings):
    per_category = defaultdict(set)
    for l in listings:
        per_category[l.category].add(l.listing_type)
    missing = {c: t for c, t in per_category.items() if t != {"kauf", "miete"}}
    assert not missing, f"categories missing a listing type: {missing}"


def test_ids_are_unique(listings):
    ids = [l.id for l in listings]
    assert len(ids) == len(set(ids))


# ------------------------------------------------------------------ coherence


def test_price_falls_as_age_and_mileage_rise_within_a_model_line():
    """The coherence guarantee. An older, higher mileage car of the same model and
    trim must never be priced above a newer, lower mileage one.

    Checked over generated data rather than the committed file alone, so the
    property is tested against the rule and not against one lucky sample.
    """
    produced = generate(seed=SEED)
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for l in produced:
        if l["listing_type"] != "kauf":
            continue
        groups[(l["brand"], l["model"], l["variant"])].append(l)

    compared = 0
    for key, group in groups.items():
        for a in group:
            for b in group:
                if a is b:
                    continue
                older_and_further = (
                    a["erstzulassung"] < b["erstzulassung"]
                    and a["kilometerstand"] > b["kilometerstand"]
                )
                if older_and_further:
                    compared += 1
                    assert a["preis_eur"] <= b["preis_eur"], (
                        f"{key}: {a['id']} is older ({a['erstzulassung']}) and has more "
                        f"mileage ({a['kilometerstand']}) than {b['id']} "
                        f"({b['erstzulassung']}, {b['kilometerstand']}) "
                        f"but costs more: {a['preis_eur']} > {b['preis_eur']}"
                    )
    assert compared > 0, "no comparable pairs found, the test would be vacuous"


def test_environmental_badge_follows_the_emissions_class(listings):
    for l in listings:
        if l.schadstoffklasse in ("Elektro", "Euro 6", "Euro 6d", "Euro 6d-TEMP", "Euro 6e"):
            assert l.umweltplakette == "gruen", f"{l.id} {l.schadstoffklasse}"
        elif l.schadstoffklasse in ("Euro 4", "Euro 5"):
            assert l.umweltplakette == "gelb", f"{l.id} {l.schadstoffklasse}"


def test_electric_cars_have_no_displacement_and_no_litre_consumption(listings):
    for l in listings:
        if l.kraftstoff == "Elektro":
            assert l.hubraum_ccm == 0, l.id
            assert l.verbrauch_l_100km is None, l.id
            assert l.verbrauch_kwh_100km is not None, l.id
            assert l.co2_g_km == 0, l.id


def test_combustion_cars_have_displacement_and_litre_consumption(listings):
    for l in listings:
        if l.kraftstoff != "Elektro":
            assert l.hubraum_ccm > 0, l.id
            assert l.verbrauch_l_100km is not None, l.id
            assert l.co2_g_km > 0, l.id


def test_power_in_metric_horsepower_matches_kilowatts(listings):
    for l in listings:
        assert abs(l.leistung_ps - round(l.leistung_kw * 1.35962)) <= 1, l.id


def test_models_only_sold_as_electric_are_never_generated_with_an_engine(listings):
    from data.vocab import NUR_ELEKTRO

    for l in listings:
        if (l.brand, l.model) in NUR_ELEKTRO:
            assert l.kraftstoff == "Elektro", f"{l.id} {l.brand} {l.model}"


def test_models_belong_to_the_category_they_are_listed_under(listings):
    allowed = {c: {(b, m) for b, m in models} for c, models in MODELLE.items()}
    for l in listings:
        assert (l.brand, l.model) in allowed[l.category], f"{l.id} {l.brand} {l.model}"


def test_inspection_date_is_not_in_the_past(listings):
    for l in listings:
        assert l.hu_faellig >= "2026-08", f"{l.id} HU {l.hu_faellig}"


def test_mileage_is_plausible_for_the_age(listings):
    for l in listings:
        age = max(l.alter_jahre(), 0.25)
        assert l.kilometerstand / age < 40_000, f"{l.id} implausible annual mileage"


# ------------------------------------------------------------------ rentals


def test_rental_listings_carry_complete_terms(listings):
    rentals = [l for l in listings if l.listing_type == "miete"]
    assert rentals
    for l in rentals:
        for field in (
            "acriss", "tagessatz_eur", "wochensatz_eur", "mindestmietdauer_tage",
            "inklusiv_km_pro_tag", "mehrkilometer_eur", "kaution_eur", "mindestalter",
            "verfuegbar_von", "verfuegbar_bis",
        ):
            assert getattr(l, field) is not None, f"{l.id} missing {field}"


def test_acriss_codes_are_four_letters(listings):
    for l in listings:
        if l.listing_type == "miete":
            assert len(l.acriss) == 4 and l.acriss.isalpha() and l.acriss.isupper(), l.id


def test_acriss_transmission_letter_matches_the_gearbox(listings):
    for l in listings:
        if l.listing_type == "miete":
            expected = "A" if l.getriebe == "Automatik" else "M"
            assert l.acriss[2] == expected, f"{l.id} {l.acriss} vs {l.getriebe}"


def test_weekly_rate_beats_seven_daily_rates(listings):
    for l in listings:
        if l.listing_type == "miete":
            assert l.wochensatz_eur < l.tagessatz_eur * 7, l.id


def test_purchase_listings_have_a_price_and_rentals_do_not(listings):
    for l in listings:
        if l.listing_type == "kauf":
            assert l.preis_eur and l.preis_eur > 0, l.id
            assert l.tagessatz_eur is None, l.id
        else:
            assert l.preis_eur is None, l.id
            assert l.tagessatz_eur and l.tagessatz_eur > 0, l.id


# ------------------------------------------------------------------ IP safety


def test_no_real_dealer_or_rental_operator_appears(listings):
    lowered = [(l.id, l.haendler.lower()) for l in listings]
    for forbidden in VERBOTENE_NAMEN:
        needle = forbidden.lower()
        hits = [lid for lid, name in lowered if needle in name]
        assert not hits, f"real operator {forbidden!r} appears in {hits}"


def test_no_bmw_group_marketplace_branding_in_operator_names(listings):
    """Manufacturer names on vehicles are factual references and are fine. A dealer
    or operator named after a manufacturer would read as an endorsement."""
    for l in listings:
        assert "bmw" not in l.haendler.lower(), l.id


# ------------------------------------------------------------------ reproducibility


def test_regeneration_from_the_seed_reproduces_the_committed_file(raw):
    """SC-010. If this fails the committed dataset is not reproducible from the repo."""
    assert generate(seed=SEED) == raw


def test_generation_is_deterministic():
    assert generate(seed=SEED) == generate(seed=SEED)


def test_a_different_seed_produces_a_different_dataset():
    assert generate(seed=SEED) != generate(seed=SEED + 1)


def test_every_generated_listing_validates_against_the_model():
    for item in generate(seed=SEED):
        Listing.model_validate(item)
