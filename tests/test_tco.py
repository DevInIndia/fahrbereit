"""Cost of ownership, with the tax formula checked against hand computed cases."""

from __future__ import annotations

from datetime import date

import pytest

from agent.listing import Listing, load_listings
from agent.tools.tco import (
    ELEKTRO_ZULASSUNG_STICHTAG,
    cost_of_ownership,
    kfz_steuer,
    rental_cost,
)

STICHTAG = date(2026, 8, 8)


def make(**overrides) -> Listing:
    base = dict(
        id="TEST-1", listing_type="kauf", brand="Volkswagen", model="Golf",
        variant="Test", category="Kompaktklasse", erstzulassung="2021-06",
        kilometerstand=50_000, leistung_kw=96, leistung_ps=130, hubraum_ccm=1_498,
        leermasse_kg=1_285, getriebe="Schaltgetriebe", kraftstoff="Benzin",
        verbrauch_l_100km=5.8, verbrauch_kwh_100km=None, co2_g_km=132,
        schadstoffklasse="Euro 6d", umweltplakette="grün", hu_faellig="2027-06",
        vorbesitzer=1, unfallfrei=True, sitzplaetze=5, kofferraum_liter=380,
        haendler="Autohaus Test", standort_plz="80339", standort_ort="München",
        preis_eur=21_490, mwst_ausweisbar=True,
    )
    base.update(overrides)
    return Listing.model_validate(base)


# ------------------------------------------------------------------ tax, petrol


def test_petrol_tax_matches_a_hand_computed_case():
    """1498 ccm petrol, 132 g/km, first registered 2021, so banded rates apply.

    Displacement: 1498 ccm is 15 started hundreds, 15 x 2.00 = 30.00
    CO2: 95 free. 95 to 115 is 20 g at 2.00 = 40.00.
         115 to 132 is 17 g at 2.20 = 37.40.
    Total 30.00 + 40.00 + 37.40 = 107.40, rounded to 107.
    """
    tax, note = kfz_steuer(make(), STICHTAG)
    assert tax == 107
    assert "1498 ccm" in note


def test_displacement_rounds_up_to_the_next_started_hundred():
    """1501 ccm is sixteen started hundreds, not fifteen."""
    a, _ = kfz_steuer(make(hubraum_ccm=1_500, co2_g_km=95), STICHTAG)
    b, _ = kfz_steuer(make(hubraum_ccm=1_501, co2_g_km=95), STICHTAG)
    assert a == 30  # 15 x 2.00
    assert b == 32  # 16 x 2.00


def test_no_co2_charge_at_or_below_the_allowance():
    tax, _ = kfz_steuer(make(hubraum_ccm=1_000, co2_g_km=95), STICHTAG)
    assert tax == 20  # 10 x 2.00, no CO2 term


# ------------------------------------------------------------------ tax, diesel


def test_diesel_uses_the_higher_displacement_rate():
    """1968 ccm diesel, 126 g/km, 2019, so the flat 2.00 per gram applies.

    Displacement: 20 started hundreds x 9.50 = 190.00
    CO2: 126 - 95 = 31 g x 2.00 = 62.00
    Total 252.
    """
    tax, _ = kfz_steuer(
        make(kraftstoff="Diesel", hubraum_ccm=1_968, co2_g_km=126, erstzulassung="2019-09"),
        STICHTAG,
    )
    assert tax == 252


def test_diesel_costs_more_than_petrol_at_identical_specification():
    petrol, _ = kfz_steuer(make(), STICHTAG)
    diesel, _ = kfz_steuer(make(kraftstoff="Diesel"), STICHTAG)
    assert diesel > petrol


# ------------------------------------------------------------------ tax, eras


def test_registrations_from_2021_use_banded_rates():
    """At 200 g/km the banded rule costs more than the old flat rule."""
    banded, _ = kfz_steuer(make(erstzulassung="2021-06", co2_g_km=200), STICHTAG)
    flat, _ = kfz_steuer(make(erstzulassung="2019-06", co2_g_km=200), STICHTAG)
    assert banded > flat


def test_the_2012_era_allowance_is_higher():
    older, _ = kfz_steuer(make(erstzulassung="2012-05", co2_g_km=120), STICHTAG)
    newer, _ = kfz_steuer(make(erstzulassung="2015-05", co2_g_km=120), STICHTAG)
    assert older < newer


def test_pre_2012_allowance_is_higher_still():
    tax, _ = kfz_steuer(make(erstzulassung="2010-05", co2_g_km=120, hubraum_ccm=1_000), STICHTAG)
    assert tax == 20  # 120 is at the 120 g/km allowance, so no CO2 term


def test_each_band_is_charged_at_its_own_rate():
    """156 g/km reaches into the fourth band, so the marginal rate is 2.90."""
    a, _ = kfz_steuer(make(hubraum_ccm=100, co2_g_km=155), STICHTAG)
    b, _ = kfz_steuer(make(hubraum_ccm=100, co2_g_km=156), STICHTAG)
    assert round(b - a) == 3  # 2.90 rounded into whole euro totals


# ------------------------------------------------------------------ tax, electric


def test_electric_registered_before_the_cutoff_is_exempt():
    tax, note = kfz_steuer(
        make(kraftstoff="Elektro", hubraum_ccm=0, co2_g_km=0, verbrauch_l_100km=None,
             verbrauch_kwh_100km=15.9, erstzulassung="2022-05", schadstoffklasse="Elektro"),
        STICHTAG,
    )
    assert tax == 0
    assert "steuerbefreit" in note


def test_the_exemption_cutoff_is_the_extended_2030_date_not_2025():
    """The Achtes Gesetz moved this. A 2025 cutoff here would be stale."""
    assert ELEKTRO_ZULASSUNG_STICHTAG == date(2030, 12, 31)


def test_electric_is_taxed_on_mass_once_the_exemption_expires():
    """Registered 2014, so the ten year exemption ended in 2024."""
    tax, note = kfz_steuer(
        make(kraftstoff="Elektro", hubraum_ccm=0, co2_g_km=0, verbrauch_l_100km=None,
             verbrauch_kwh_100km=16.0, erstzulassung="2014-03", leermasse_kg=1_600,
             schadstoffklasse="Elektro"),
        STICHTAG,
    )
    assert tax > 0
    assert "Ermäßigung" in note


def test_the_mass_rate_carries_the_fifty_percent_reduction():
    """1600 kg is eight started 200 kg units at 5.625, halved."""
    tax, _ = kfz_steuer(
        make(kraftstoff="Elektro", hubraum_ccm=0, co2_g_km=0, verbrauch_l_100km=None,
             verbrauch_kwh_100km=16.0, erstzulassung="2014-03", leermasse_kg=1_600,
             schadstoffklasse="Elektro"),
        STICHTAG,
    )
    assert tax == round(8 * 5.625 * 0.5)


# ------------------------------------------------------------------ totals


def test_itemised_terms_sum_to_the_reported_total():
    """The identity that lets a user check the figure instead of trusting it."""
    tco = cost_of_ownership(make(), 15_000, STICHTAG)
    assert (
        tco.kfz_steuer_5j_eur
        + tco.versicherung_5j_eur
        + tco.energie_5j_eur
        + tco.wartung_5j_eur
        + tco.wertverlust_eur
        == tco.gesamt_5j_eur
    )


def test_the_displayed_line_items_also_sum_to_the_total():
    tco = cost_of_ownership(make(), 15_000, STICHTAG)
    assert sum(v for _, v in tco.posten()) == tco.gesamt_5j_eur


def test_annual_figures_are_five_times_the_five_year_figures():
    tco = cost_of_ownership(make(), 15_000, STICHTAG)
    assert tco.kfz_steuer_5j_eur == tco.kfz_steuer_jahr_eur * 5
    assert tco.energie_5j_eur == tco.energie_jahr_eur * 5
    assert tco.versicherung_5j_eur == tco.versicherung_jahr_eur * 5


def test_higher_annual_mileage_costs_more_energy():
    low = cost_of_ownership(make(), 8_000, STICHTAG)
    high = cost_of_ownership(make(), 30_000, STICHTAG)
    assert high.energie_5j_eur > low.energie_5j_eur
    assert high.gesamt_5j_eur > low.gesamt_5j_eur


def test_electric_energy_is_cheaper_than_petrol_at_the_same_mileage():
    petrol = cost_of_ownership(make(), 20_000, STICHTAG)
    electric = cost_of_ownership(
        make(kraftstoff="Elektro", hubraum_ccm=0, co2_g_km=0, verbrauch_l_100km=None,
             verbrauch_kwh_100km=16.0, schadstoffklasse="Elektro"),
        20_000,
        STICHTAG,
    )
    assert electric.energie_5j_eur < petrol.energie_5j_eur


def test_residual_value_is_below_the_purchase_price():
    tco = cost_of_ownership(make(), 15_000, STICHTAG)
    assert 0 < tco.restwert_eur < 21_490
    assert tco.wertverlust_eur == 21_490 - tco.restwert_eur


def test_the_ownership_model_refuses_a_rental():
    """The defect this replaced: five years of ownership cost billed to a renter.

    Rejecting the call outright is what stops it coming back. A rental that quietly
    returned a slightly wrong number is far worse than one that raises.
    """
    rental = next(l for l in load_listings() if l.listing_type == "miete")
    with pytest.raises(ValueError, match="rental_cost"):
        cost_of_ownership(rental, 15_000, STICHTAG)


def test_older_and_higher_mileage_cars_cost_more_to_maintain():
    young = cost_of_ownership(make(erstzulassung="2024-01", kilometerstand=20_000), 15_000, STICHTAG)
    old = cost_of_ownership(make(erstzulassung="2015-01", kilometerstand=180_000), 15_000, STICHTAG)
    assert old.wartung_5j_eur > young.wartung_5j_eur


def test_every_purchase_in_the_dataset_produces_a_sane_total():
    for listing in load_listings():
        if listing.listing_type != "kauf":
            continue
        tco = cost_of_ownership(listing, 15_000, STICHTAG)
        assert tco.gesamt_5j_eur > 0
        assert tco.kfz_steuer_jahr_eur >= 0
        assert sum(v for _, v in tco.posten()) == tco.gesamt_5j_eur


def test_the_estimate_disclaimer_is_always_present():
    """Tax is exact, the rest is estimated. The interface must never blur that."""
    tco = cost_of_ownership(make(), 15_000, STICHTAG)
    assert "Schätzungen" in tco.schaetzung_hinweis
    assert "KraftStG" in tco.schaetzung_hinweis


def test_cost_of_ownership_is_deterministic():
    a = cost_of_ownership(make(), 15_000, STICHTAG)
    b = cost_of_ownership(make(), 15_000, STICHTAG)
    assert a.model_dump() == b.model_dump()


# ------------------------------------------------------------------ rental cost


def rental(**overrides) -> Listing:
    """A rental listing with round numbers, so the arithmetic can be checked by hand."""
    base = dict(
        id="TEST-M1", listing_type="miete", brand="Volkswagen", model="Caddy",
        variant="Maxi", category="Van/Großraumlimousine", erstzulassung="2024-03",
        kilometerstand=30_000, leistung_kw=90, leistung_ps=122, hubraum_ccm=1_498,
        leermasse_kg=1_600, getriebe="Schaltgetriebe", kraftstoff="Benzin",
        verbrauch_l_100km=7.0, verbrauch_kwh_100km=None, co2_g_km=160,
        schadstoffklasse="Euro 6d", umweltplakette="grün", hu_faellig="2027-03",
        vorbesitzer=1, unfallfrei=True, sitzplaetze=5, kofferraum_liter=900,
        haendler="Mietwagen Test", standort_plz="20095", standort_ort="Hamburg",
        acriss="CVMR", tagessatz_eur=60, wochensatz_eur=300,
        mindestmietdauer_tage=1, inklusiv_km_pro_tag=150, mehrkilometer_eur=0.30,
        kaution_eur=500, mindestalter=21,
        verfuegbar_von="2026-08-01", verfuegbar_bis="2026-12-31",
    )
    base.update(overrides)
    return Listing.model_validate(base)


def test_a_renter_is_charged_no_vehicle_tax_insurance_or_depreciation():
    """The whole point of the model. None of those four appear in the total."""
    cost = rental_cost(rental(), tage=3)
    assert cost.gesamt_miete_eur == (
        cost.grundpreis_eur + cost.energie_eur + cost.mehrkilometer_eur
    )
    labels = [name for name, _ in cost.posten("de")]
    assert "Kfz-Steuer" not in labels
    assert "Versicherung" not in labels
    assert "Wartung" not in labels
    assert "Wertverlust" not in labels


def test_the_base_price_is_days_times_the_daily_rate():
    cost = rental_cost(rental(), tage=3, erwartete_km=450)
    assert cost.grundpreis_eur == 180  # 3 x 60
    assert "3 x Tagessatz 60 EUR" in cost.grundpreis_basis


def test_the_weekly_rate_is_used_when_it_beats_the_daily_rate():
    """Ten days: one week at 300 plus three days at 60 is 480, against 600 daily."""
    cost = rental_cost(rental(), tage=10, erwartete_km=0)
    assert cost.grundpreis_eur == 480
    assert "Wochensatz" in cost.grundpreis_basis


def test_the_daily_rate_wins_when_the_weekly_rate_is_not_cheaper():
    cost = rental_cost(rental(wochensatz_eur=999), tage=8, erwartete_km=0)
    assert cost.grundpreis_eur == 480  # 8 x 60, the weekly structure is worse


def test_excess_kilometres_are_charged_only_above_the_included_allowance():
    """150 km per day included. Three days is 450 included; 600 driven leaves 150."""
    inside = rental_cost(rental(), tage=3, erwartete_km=450)
    assert inside.mehrkilometer_km == 0
    assert inside.mehrkilometer_eur == 0

    outside = rental_cost(rental(), tage=3, erwartete_km=600)
    assert outside.mehrkilometer_km == 150
    assert outside.mehrkilometer_eur == 45  # 150 x 0.30


def test_the_deposit_is_reported_but_never_added_to_the_total():
    """Refundable money is not a cost. Adding it would overstate the rental."""
    cost = rental_cost(rental(), tage=3, erwartete_km=450)
    assert cost.kaution_eur == 500
    assert cost.gesamt_miete_eur < 500 + cost.grundpreis_eur
    assert sum(v for _, v in cost.posten()) == cost.gesamt_miete_eur
    assert "erstattungsfähig" in cost.kaution_hinweis


def test_fuel_is_costed_over_the_rental_distance_not_over_a_year():
    """600 km at 7.0 l per 100 km at 1.82 EUR is 76 EUR, not a year's worth."""
    cost = rental_cost(rental(), tage=3, erwartete_km=600)
    assert cost.energie_eur == 76


def test_a_longer_rental_costs_more():
    short = rental_cost(rental(), tage=2)
    long = rental_cost(rental(), tage=5)
    assert long.gesamt_miete_eur > short.gesamt_miete_eur


def test_a_rental_below_its_minimum_duration_is_flagged():
    cost = rental_cost(rental(mindestmietdauer_tage=3), tage=1)
    assert cost.unter_mindestmietdauer is True
    assert rental_cost(rental(mindestmietdauer_tage=3), tage=3).unter_mindestmietdauer is False


def test_the_rental_model_refuses_a_purchase_listing():
    with pytest.raises(ValueError, match="cost_of_ownership"):
        rental_cost(make())


def test_rental_cost_is_deterministic():
    a = rental_cost(rental(), tage=4)
    b = rental_cost(rental(), tage=4)
    assert a.model_dump() == b.model_dump()


def test_every_rental_in_the_dataset_produces_a_sane_total():
    for listing in load_listings():
        if listing.listing_type != "miete":
            continue
        cost = rental_cost(listing, tage=3)
        assert cost.gesamt_miete_eur > 0
        assert sum(v for _, v in cost.posten()) == cost.gesamt_miete_eur
        assert cost.kaution_eur not in [v for _, v in cost.posten()]


def test_the_rental_disclaimer_names_who_carries_the_omitted_costs():
    de = rental_cost(rental(), tage=3, lang="de")
    en = rental_cost(rental(), tage=3, lang="en")
    assert "Vermieter" in de.miet_hinweis
    assert "operator" in en.miet_hinweis
    assert de.gesamt_miete_eur == en.gesamt_miete_eur, "language changed a number"
