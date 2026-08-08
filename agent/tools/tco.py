"""Five year cost of ownership, German conditions.

Motor vehicle tax is a published formula and is computed exactly. Everything else is
a segment estimate and is labelled as one. The distinction matters: a user shown a
tax figure is being told a fact, and a user shown an insurance figure is being told a
guess. Conflating them would be the same class of error as letting the model invent
the ranking.

The formula, its source and the two recorded assumptions are in
specs/001-fahrbereit-agent/research.md.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel

from agent.listing import Listing
from agent.state import InterviewState

JAHRE = 5

# Paragraph 9 KraftStG, read 2026-08-08. Rate per angefangene 100 ccm.
HUBRAUM_SATZ = {"Benzin": 2.00, "Hybrid": 2.00, "Plug-in-Hybrid": 2.00, "Diesel": 9.50}

# Banded CO2 rates for first registrations from 2021. Each band applies only to the
# portion of the figure inside it, so the charge is progressive.
CO2_BAENDER: tuple[tuple[int, float], ...] = (
    (115, 2.00),
    (135, 2.20),
    (155, 2.50),
    (175, 2.90),
    (195, 3.40),
    (10_000, 4.00),
)

# Electric vehicles: exemption runs ten years from first registration, qualifies for
# registrations up to the end of 2030, and is capped at the end of 2035.
ELEKTRO_BEFREIUNG_JAHRE = 10
ELEKTRO_ZULASSUNG_STICHTAG = date(2030, 12, 31)
ELEKTRO_BEFREIUNG_ENDE = date(2035, 12, 31)

# Mass based rate for electric vehicles after the exemption. Recorded in research.md
# as an assumption rather than as a confirmed statutory figure.
MASSE_STUFEN: tuple[tuple[int, float], ...] = ((2_000, 5.625), (3_000, 6.01), (10**9, 6.39))

# Energy prices, stated so the reader can disagree with them explicitly.
PREIS_BENZIN_EUR_L = 1.82
PREIS_DIESEL_EUR_L = 1.71
PREIS_STROM_EUR_KWH = 0.39

# Segment averages. Estimates, and presented as estimates.
VERSICHERUNG_BASIS: dict[str, int] = {
    "Kleinstwagen": 380, "Kleinwagen": 430, "Kompaktklasse": 520, "Mittelklasse": 650,
    "Obere Mittelklasse": 850, "Oberklasse": 1_250, "SUV/Gelaendewagen": 720,
    "Kombi": 590, "Van/Grossraumlimousine": 640, "Sportwagen/Cabrio": 980,
}
WARTUNG_BASIS: dict[str, int] = {
    "Kleinstwagen": 320, "Kleinwagen": 380, "Kompaktklasse": 460, "Mittelklasse": 600,
    "Obere Mittelklasse": 820, "Oberklasse": 1_300, "SUV/Gelaendewagen": 700,
    "Kombi": 540, "Van/Grossraumlimousine": 640, "Sportwagen/Cabrio": 950,
}
# Annual value retention over the five year horizon, by segment.
RESTWERT_RATE: dict[str, float] = {
    "Kleinstwagen": 0.87, "Kleinwagen": 0.87, "Kompaktklasse": 0.86,
    "Mittelklasse": 0.84, "Obere Mittelklasse": 0.82, "Oberklasse": 0.79,
    "SUV/Gelaendewagen": 0.86, "Kombi": 0.86, "Van/Grossraumlimousine": 0.85,
    "Sportwagen/Cabrio": 0.88,
}

STANDARD_JAHRESFAHRLEISTUNG = 15_000


class CostOfOwnership(BaseModel):
    """Itemised, so the total can be checked rather than believed."""

    kfz_steuer_jahr_eur: int
    kfz_steuer_5j_eur: int
    versicherung_jahr_eur: int
    versicherung_5j_eur: int
    energie_jahr_eur: int
    energie_5j_eur: int
    wartung_5j_eur: int
    restwert_eur: int
    wertverlust_eur: int
    gesamt_5j_eur: int
    jahresfahrleistung_km: int
    steuer_hinweis: str
    schaetzung_hinweis: str = (
        "Versicherung, Wartung und Restwert sind Schaetzungen nach Segmentmittelwerten, "
        "keine Angebote. Die Kfz-Steuer ist nach Paragraph 9 KraftStG exakt berechnet."
    )

    def posten(self) -> list[tuple[str, int]]:
        return [
            ("Kfz-Steuer", self.kfz_steuer_5j_eur),
            ("Versicherung", self.versicherung_5j_eur),
            ("Energie", self.energie_5j_eur),
            ("Wartung", self.wartung_5j_eur),
            ("Wertverlust", self.wertverlust_eur),
        ]


def _co2_anteil(co2: int, freibetrag: int, gestaffelt: bool) -> float:
    """The carbon dioxide term. Banded from 2021, flat before."""
    ueber = max(0, co2 - freibetrag)
    if ueber == 0:
        return 0.0
    if not gestaffelt:
        return ueber * 2.00

    total = 0.0
    untergrenze = freibetrag
    for obergrenze, satz in CO2_BAENDER:
        if co2 <= untergrenze:
            break
        anteil = min(co2, obergrenze) - untergrenze
        if anteil > 0:
            total += anteil * satz
        untergrenze = obergrenze
    return total


def _elektro_steuer(listing: Listing, stichtag: date) -> tuple[int, str]:
    ez = date(listing.erstzulassung_jahr, listing.erstzulassung_monat, 1)

    if ez <= ELEKTRO_ZULASSUNG_STICHTAG:
        ende = min(
            date(ez.year + ELEKTRO_BEFREIUNG_JAHRE, ez.month, 1), ELEKTRO_BEFREIUNG_ENDE
        )
        if stichtag <= ende:
            return 0, (
                f"Reines Elektrofahrzeug, steuerbefreit bis {ende.strftime('%m/%Y')} "
                f"(Achtes Gesetz zur Aenderung des KraftStG)."
            )

    # Exemption spent: mass based rate, then reduced by half.
    masse = listing.leermasse_kg
    betrag = 0.0
    untergrenze = 0
    for obergrenze, satz in MASSE_STUFEN:
        if masse <= untergrenze:
            break
        anteil_kg = min(masse, obergrenze) - untergrenze
        einheiten = -(-anteil_kg // 200)  # angefangene 200 kg
        betrag += einheiten * satz
        untergrenze = obergrenze
    return int(round(betrag * 0.5)), (
        "Reines Elektrofahrzeug nach Ablauf der Befreiung, Gewichtsbesteuerung "
        "mit 50 Prozent Ermaessigung."
    )


def kfz_steuer(listing: Listing, stichtag: Optional[date] = None) -> tuple[int, str]:
    """Annual German motor vehicle tax, in euro. Exact, not estimated."""
    stichtag = stichtag or date.today()

    if listing.kraftstoff == "Elektro":
        return _elektro_steuer(listing, stichtag)

    einheiten = -(-listing.hubraum_ccm // 100)  # angefangene 100 ccm
    satz = HUBRAUM_SATZ.get(listing.kraftstoff, 2.00)
    hubraum_teil = einheiten * satz

    jahr = listing.erstzulassung_jahr
    if jahr >= 2021:
        freibetrag, gestaffelt = 95, True
        regel = "Staffelung ab EZ 2021"
    elif jahr >= 2014:
        freibetrag, gestaffelt = 95, False
        regel = "Pauschal 2,00 EUR/g ab EZ 07/2014"
    elif jahr >= 2012:
        freibetrag, gestaffelt = 110, False
        regel = "Freibetrag 110 g/km, EZ 2012 bis 2013"
    else:
        freibetrag, gestaffelt = 120, False
        regel = "Freibetrag 120 g/km, EZ bis 2011"

    co2_teil = _co2_anteil(listing.co2_g_km, freibetrag, gestaffelt)
    gesamt = int(round(hubraum_teil + co2_teil))
    hinweis = (
        f"{einheiten} x {satz:.2f} EUR je angefangene 100 ccm "
        f"({listing.hubraum_ccm} ccm) plus CO2-Anteil auf "
        f"{max(0, listing.co2_g_km - freibetrag)} g ueber {freibetrag} g/km. {regel}."
    )
    return gesamt, hinweis


def _energie_jahr(listing: Listing, km: int) -> int:
    if listing.kraftstoff == "Elektro":
        verbrauch = listing.verbrauch_kwh_100km or 18.0
        return int(round(km / 100 * verbrauch * PREIS_STROM_EUR_KWH))
    verbrauch = listing.verbrauch_l_100km or 6.5
    preis = PREIS_DIESEL_EUR_L if listing.kraftstoff == "Diesel" else PREIS_BENZIN_EUR_L
    return int(round(km / 100 * verbrauch * preis))


def _versicherung_jahr(listing: Listing) -> int:
    basis = VERSICHERUNG_BASIS.get(listing.category, 550)
    leistungszuschlag = 1.0 + max(0, listing.leistung_kw - 100) / 100 * 0.35
    return int(round(basis * leistungszuschlag))


def _wartung_5j(listing: Listing, stichtag: Optional[date] = None) -> int:
    basis = WARTUNG_BASIS.get(listing.category, 500)
    alter = listing.alter_jahre(stichtag)
    alterszuschlag = 1.0 + min(alter, 15) * 0.06
    verschleiss = 1.25 if listing.kilometerstand > 120_000 else 1.0
    elektro_rabatt = 0.72 if listing.kraftstoff == "Elektro" else 1.0
    return int(round(basis * alterszuschlag * verschleiss * elektro_rabatt * JAHRE))


def cost_of_ownership(
    listing: Listing,
    jahresfahrleistung_km: int = STANDARD_JAHRESFAHRLEISTUNG,
    stichtag: Optional[date] = None,
) -> CostOfOwnership:
    """Five year cost of ownership for one listing.

    Rentals have no purchase price, so depreciation and residual value are zero and
    the figure is a running cost comparison rather than an ownership one.
    """
    km = max(jahresfahrleistung_km, 1_000)

    steuer_jahr, steuer_hinweis = kfz_steuer(listing, stichtag)
    versicherung_jahr = _versicherung_jahr(listing)
    energie_jahr = _energie_jahr(listing, km)
    wartung = _wartung_5j(listing, stichtag)

    preis = listing.preis_eur or 0
    if preis:
        rate = RESTWERT_RATE.get(listing.category, 0.85)
        restwert = int(round(preis * rate**JAHRE))
    else:
        restwert = 0
    wertverlust = preis - restwert

    gesamt = (
        steuer_jahr * JAHRE
        + versicherung_jahr * JAHRE
        + energie_jahr * JAHRE
        + wartung
        + wertverlust
    )

    return CostOfOwnership(
        kfz_steuer_jahr_eur=steuer_jahr,
        kfz_steuer_5j_eur=steuer_jahr * JAHRE,
        versicherung_jahr_eur=versicherung_jahr,
        versicherung_5j_eur=versicherung_jahr * JAHRE,
        energie_jahr_eur=energie_jahr,
        energie_5j_eur=energie_jahr * JAHRE,
        wartung_5j_eur=wartung,
        restwert_eur=restwert,
        wertverlust_eur=wertverlust,
        gesamt_5j_eur=gesamt,
        jahresfahrleistung_km=km,
        steuer_hinweis=steuer_hinweis,
    )


def tco_for_state(listing: Listing, state: InterviewState) -> int:
    """Adapter for the ranking pipeline's injected cost function."""
    km = state.jahresfahrleistung_km.value or STANDARD_JAHRESFAHRLEISTUNG
    return cost_of_ownership(listing, km).gesamt_5j_eur
