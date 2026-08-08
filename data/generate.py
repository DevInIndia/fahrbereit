"""Seeded generator for the mock marketplace.

Deterministic: the same seed reproduces the same file byte for byte. That is what
makes the committed dataset a reproducible artifact rather than a blob.

The design rule that matters is coherence. Price is a pure function of the segment
base, the brand level, the trim, the age and the mileage. Nothing else touches it.
Owner count and accident history are derived from age and mileage rather than drawn
independently, which keeps them plausible without letting them break the guarantee
that an older, higher mileage car of the same model and trim never costs more than a
newer, lower mileage one.

Run:  python -m data.generate
"""

from __future__ import annotations

import json
import random
from datetime import date
from pathlib import Path

from data.vocab import (
    AUSSTATTUNG,
    HAENDLER_NAME,
    HAENDLER_PRAEFIX,
    MARKE_NIVEAU,
    MODELLE,
    NUR_ELEKTRO,
    ORTE,
    SEGMENT,
    VERMIETER,
    acriss_code,
)

SEED = 20260808
OUTPUT = Path(__file__).resolve().parent / "listings.json"

# Generation is anchored to a fixed date so ages and inspection dates are stable
# across runs and across machines. Not today(), which would make output drift.
STICHTAG = date(2026, 8, 8)

ZIEL_ANZAHL = 280
MIETE_ANTEIL = 0.22


def _lerp(low: float, high: float, t: float) -> float:
    return low + (high - low) * t


def _preis(segment_basis: int, niveau: float, trim_index: int, alter: float, km: int) -> int:
    """Price from base, brand level, trim, age and mileage. Nothing else.

    Age uses a declining curve rather than straight line depreciation, because a car
    loses most of its value early. Mileage is a separate penalty so two cars of the
    same age can still separate on the clock.
    """
    neupreis = segment_basis * niveau * (1.0 + 0.075 * trim_index)
    alterswert = 0.86 ** alter
    km_faktor = max(0.45, 1.0 - (km / 100_000) * 0.16)
    preis = neupreis * alterswert * km_faktor
    return int(round(max(preis, 1_200) / 10) * 10)


def _schadstoffklasse(jahr: int) -> tuple[str, str]:
    if jahr >= 2021:
        return "Euro 6d", "gruen"
    if jahr >= 2019:
        return "Euro 6d-TEMP", "gruen"
    if jahr >= 2015:
        return "Euro 6", "gruen"
    if jahr >= 2011:
        return "Euro 5", "gelb"
    return "Euro 4", "gelb"


def _generate_one(
    rng: random.Random,
    index: int,
    kategorie: str,
    ist_miete: bool,
    modell_wahl: tuple[str, str] | None = None,
) -> dict:
    spec = SEGMENT[kategorie]
    marke, modell = modell_wahl or rng.choice(MODELLE[kategorie])
    niveau = MARKE_NIVEAU.get(marke, 1.0)

    trim_index = rng.randrange(len(AUSSTATTUNG))
    trim = AUSSTATTUNG[trim_index]

    # Rentals are fleet cars: young and low mileage. Purchases span the market.
    if ist_miete:
        alter_monate = rng.randrange(3, 30)
        jahres_km = rng.randrange(12_000, 26_000)
    else:
        alter_monate = rng.randrange(6, 144)
        jahres_km = rng.randrange(7_000, 24_000)

    alter = alter_monate / 12.0
    ez_jahr = STICHTAG.year - (alter_monate // 12)
    ez_monat = STICHTAG.month - (alter_monate % 12)
    if ez_monat <= 0:
        ez_monat += 12
        ez_jahr -= 1
    km = max(500, int(alter * jahres_km))

    elektro = (marke, modell) in NUR_ELEKTRO
    if elektro:
        kraftstoff = "Elektro"
    else:
        kraftstoff = rng.choices(
            ["Benzin", "Diesel", "Hybrid", "Plug-in-Hybrid"], weights=[52, 26, 16, 6]
        )[0]

    # Power scales with trim level, so a Sport trim is not weaker than a Basis one.
    t = _lerp(0.15, 0.95, trim_index / max(len(AUSSTATTUNG) - 1, 1))
    kw = int(round(_lerp(spec["kw"][0], spec["kw"][1], t)))
    ps = int(round(kw * 1.35962))

    masse = int(round(_lerp(spec["masse"][0], spec["masse"][1], t)))
    if elektro:
        masse += 260  # battery mass, which is what makes electric cars heavy
        hubraum = 0
    else:
        hubraum = int(round(_lerp(spec["hubraum"][0], spec["hubraum"][1], t)))

    getriebe = "Automatik" if (elektro or rng.random() < 0.46) else "Schaltgetriebe"

    if elektro:
        verbrauch_l = None
        verbrauch_kwh = round(_lerp(spec["kwh"][0], spec["kwh"][1], t), 1)
        co2 = 0
        schadstoff, plakette = "Elektro", "gruen"
    else:
        verbrauch_l = round(_lerp(spec["verbrauch"][0], spec["verbrauch"][1], t), 1)
        if kraftstoff == "Diesel":
            verbrauch_l = round(verbrauch_l * 0.84, 1)
        elif kraftstoff in ("Hybrid", "Plug-in-Hybrid"):
            verbrauch_l = round(verbrauch_l * 0.72, 1)
        verbrauch_kwh = None
        faktor = 26.4 if kraftstoff == "Diesel" else 23.2
        co2 = int(round(verbrauch_l * faktor))
        schadstoff, plakette = _schadstoffklasse(ez_jahr)

    sitze = rng.randint(spec["sitze"][0], spec["sitze"][1])
    kofferraum = int(round(_lerp(spec["kofferraum"][0], spec["kofferraum"][1], rng.random())))

    # Derived from age and mileage, not drawn independently, so they stay plausible
    # while leaving price strictly monotonic in age and mileage.
    vorbesitzer = 1 + int(alter // 4) + (1 if km > 120_000 else 0)
    unfallfrei = not (alter > 6 and km > 130_000 and (index % 7 == 0))

    hu_jahr = ez_jahr + 3 + 2 * int(alter // 2)
    while hu_jahr < STICHTAG.year:
        hu_jahr += 2
    hu = f"{hu_jahr:04d}-{ez_monat:02d}"

    plz, ort = rng.choice(ORTE)

    listing: dict = {
        "id": f"FB-{index:05d}",
        "listing_type": "miete" if ist_miete else "kauf",
        "brand": marke,
        "model": modell,
        "variant": f"{kw} kW {trim}",
        "category": kategorie,
        "erstzulassung": f"{ez_jahr:04d}-{ez_monat:02d}",
        "kilometerstand": km,
        "leistung_kw": kw,
        "leistung_ps": ps,
        "hubraum_ccm": hubraum,
        "leermasse_kg": masse,
        "getriebe": getriebe,
        "kraftstoff": kraftstoff,
        "verbrauch_l_100km": verbrauch_l,
        "verbrauch_kwh_100km": verbrauch_kwh,
        "co2_g_km": co2,
        "schadstoffklasse": schadstoff,
        "umweltplakette": plakette,
        "hu_faellig": hu,
        "vorbesitzer": vorbesitzer,
        "unfallfrei": unfallfrei,
        "sitzplaetze": sitze,
        "kofferraum_liter": kofferraum,
        "standort_plz": plz,
        "standort_ort": ort,
    }

    preis = _preis(spec["basispreis"], niveau, trim_index, alter, km)

    if ist_miete:
        listing["haendler"] = rng.choice(VERMIETER)
        listing["acriss"] = acriss_code(kategorie, getriebe, kraftstoff)
        tagessatz = max(19, int(round(preis / 420 / 5) * 5))
        listing["tagessatz_eur"] = tagessatz
        listing["wochensatz_eur"] = int(round(tagessatz * 5.9 / 5) * 5)
        listing["mindestmietdauer_tage"] = rng.choice([1, 1, 2, 3])
        listing["inklusiv_km_pro_tag"] = rng.choice([150, 200, 250, 300])
        listing["mehrkilometer_eur"] = round(rng.uniform(0.18, 0.39), 2)
        listing["kaution_eur"] = int(round(tagessatz * rng.choice([8, 10, 12]) / 50) * 50)
        listing["mindestalter"] = rng.choice([21, 21, 23, 25])
        listing["verfuegbar_von"] = "2026-08-01"
        listing["verfuegbar_bis"] = rng.choice(
            ["2026-10-31", "2026-11-30", "2026-12-15", "2026-12-31", "2027-03-31"]
        )
    else:
        praefix = rng.choice(HAENDLER_PRAEFIX)
        listing["haendler"] = f"{praefix} {rng.choice(HAENDLER_NAME)}"
        listing["preis_eur"] = preis
        listing["mwst_ausweisbar"] = rng.random() < 0.68

    return listing


def generate(seed: int = SEED, anzahl: int = ZIEL_ANZAHL) -> list[dict]:
    """Produce the marketplace. Same seed, same output, every time."""
    rng = random.Random(seed)
    kategorien = list(SEGMENT)
    listings: list[dict] = []
    index = 1

    # Floor first, and by enumeration rather than by sampling. Drawing at random
    # left a category one brand short of the required ten, because random draws do
    # not promise coverage. Walking the model list does.
    for kategorie in kategorien:
        modelle = MODELLE[kategorie]
        for n, modell_wahl in enumerate(modelle):
            listings.append(
                _generate_one(rng, index, kategorie, n % 5 == 4, modell_wahl=modell_wahl)
            )
            index += 1
        # A second pass over the first few models, so every category also carries a
        # spread of ages and trims for the same nameplate.
        for n, modell_wahl in enumerate(modelle[: max(4, 14 - len(modelle))]):
            listings.append(
                _generate_one(rng, index, kategorie, n % 4 == 3, modell_wahl=modell_wahl)
            )
            index += 1

    while len(listings) < anzahl:
        kategorie = rng.choice(kategorien)
        ist_miete = rng.random() < MIETE_ANTEIL
        listings.append(_generate_one(rng, index, kategorie, ist_miete))
        index += 1

    return listings


def write(path: Path = OUTPUT, seed: int = SEED, anzahl: int = ZIEL_ANZAHL) -> list[dict]:
    listings = generate(seed, anzahl)
    path.write_text(
        json.dumps(listings, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
    )
    return listings


if __name__ == "__main__":
    produced = write()
    kategorien = {l["category"] for l in produced}
    print(f"wrote {len(produced)} listings to {OUTPUT}")
    print(f"categories: {len(kategorien)}")
    for kategorie in sorted(kategorien):
        in_cat = [l for l in produced if l["category"] == kategorie]
        marken = {l["brand"] for l in in_cat}
        miete = sum(1 for l in in_cat if l["listing_type"] == "miete")
        print(
            f"  {kategorie:<26} {len(in_cat):>4} listings  "
            f"{len(marken):>3} brands  {miete:>3} rental"
        )
