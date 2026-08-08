"""The marketplace listing model.

German trade vocabulary throughout, so a value can be traced from the dataset to a
rendered cell without translation. Umlauts are transliterated in data values, ae oe
ue ss, to keep the dataset free of encoding accidents across Windows terminals,
Docker images and browsers.
"""

from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "listings.json"

Kategorie = Literal[
    "Kleinstwagen",
    "Kleinwagen",
    "Kompaktklasse",
    "Mittelklasse",
    "Obere Mittelklasse",
    "Oberklasse",
    "SUV/Gelaendewagen",
    "Kombi",
    "Van/Grossraumlimousine",
    "Sportwagen/Cabrio",
]

KATEGORIEN: tuple[str, ...] = (
    "Kleinstwagen",
    "Kleinwagen",
    "Kompaktklasse",
    "Mittelklasse",
    "Obere Mittelklasse",
    "Oberklasse",
    "SUV/Gelaendewagen",
    "Kombi",
    "Van/Grossraumlimousine",
    "Sportwagen/Cabrio",
)

Kraftstoff = Literal["Benzin", "Diesel", "Elektro", "Hybrid", "Plug-in-Hybrid"]
Getriebe = Literal["Schaltgetriebe", "Automatik"]
Plakette = Literal["gruen", "gelb", "rot"]

# Ordered best to worst. A requirement for green admits only green.
PLAKETTEN_RANG: dict[str, int] = {"gruen": 3, "gelb": 2, "rot": 1}


class Listing(BaseModel):
    """One vehicle offered for purchase or rental."""

    id: str
    listing_type: Literal["kauf", "miete"]

    brand: str
    model: str
    variant: str
    category: Kategorie

    erstzulassung: str  # YYYY-MM
    kilometerstand: int
    leistung_kw: int
    leistung_ps: int
    hubraum_ccm: int  # zero for battery electric
    leermasse_kg: int

    getriebe: Getriebe
    kraftstoff: Kraftstoff
    verbrauch_l_100km: Optional[float] = None
    verbrauch_kwh_100km: Optional[float] = None
    co2_g_km: int
    schadstoffklasse: str
    umweltplakette: Plakette
    hu_faellig: str  # YYYY-MM

    vorbesitzer: int
    unfallfrei: bool
    sitzplaetze: int
    kofferraum_liter: int

    haendler: str
    standort_plz: str
    standort_ort: str

    # kauf only
    preis_eur: Optional[int] = None
    mwst_ausweisbar: Optional[bool] = None

    # miete only
    acriss: Optional[str] = None
    tagessatz_eur: Optional[int] = None
    wochensatz_eur: Optional[int] = None
    mindestmietdauer_tage: Optional[int] = None
    inklusiv_km_pro_tag: Optional[int] = None
    mehrkilometer_eur: Optional[float] = None
    kaution_eur: Optional[int] = None
    mindestalter: Optional[int] = None
    verfuegbar_von: Optional[str] = None
    verfuegbar_bis: Optional[str] = None

    # ------------------------------------------------------------------ derived

    @property
    def ist_elektro(self) -> bool:
        return self.kraftstoff == "Elektro"

    @property
    def erstzulassung_jahr(self) -> int:
        return int(self.erstzulassung[:4])

    @property
    def erstzulassung_monat(self) -> int:
        return int(self.erstzulassung[5:7])

    def alter_jahre(self, stichtag: Optional[date] = None) -> float:
        today = stichtag or date.today()
        months = (today.year - self.erstzulassung_jahr) * 12 + (
            today.month - self.erstzulassung_monat
        )
        return max(months, 0) / 12.0

    def hu_monate_verbleibend(self, stichtag: Optional[date] = None) -> int:
        today = stichtag or date.today()
        jahr, monat = int(self.hu_faellig[:4]), int(self.hu_faellig[5:7])
        return (jahr - today.year) * 12 + (monat - today.month)

    @property
    def bezeichnung(self) -> str:
        return f"{self.brand} {self.model} {self.variant}".strip()

    def preis_referenz(self) -> int:
        """One comparable number per listing, whatever the listing type.

        Purchase uses the asking price. Rental uses the daily rate, so the two are
        never compared against each other, only within a type.
        """
        if self.listing_type == "kauf":
            return self.preis_eur or 0
        return self.tagessatz_eur or 0


@lru_cache(maxsize=1)
def load_listings(path: str | Path | None = None) -> tuple[Listing, ...]:
    """Load the marketplace. Cached, because it is read on every ranking call."""
    source = Path(path) if path else DATA_FILE
    raw = json.loads(source.read_text(encoding="utf-8"))
    return tuple(Listing.model_validate(item) for item in raw)


def clear_cache() -> None:
    load_listings.cache_clear()
