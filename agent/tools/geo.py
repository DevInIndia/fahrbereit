"""Approximate distance between German postal codes.

A deliberate approximation. Postal code areas are mapped to the centroid of their
two digit region and distance is great circle between centroids, so two listings in
the same region read as nearby and one across the country reads as far. That is the
resolution the dealer distance dimension actually needs.

It is not a routing engine and does not claim to be. Anything finer would require a
postal code geodata set, which is weight this project does not need to carry.
"""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

# Two digit postal regions to approximate centroids. Covers the regions the dataset
# uses; anything else falls back to the one digit zone below.
PLZ2_CENTROIDS: dict[str, tuple[float, float]] = {
    "01": (51.05, 13.74),  # Dresden
    "04": (51.34, 12.37),  # Leipzig
    "10": (52.52, 13.40),  # Berlin
    "12": (52.46, 13.43),
    "20": (53.55, 9.99),   # Hamburg
    "22": (53.57, 9.94),
    "28": (53.08, 8.81),   # Bremen
    "30": (52.38, 9.73),   # Hannover
    "40": (51.23, 6.78),   # Duesseldorf
    "44": (51.51, 7.47),   # Dortmund
    "50": (50.94, 6.96),   # Koeln
    "53": (50.73, 7.10),   # Bonn
    "60": (50.11, 8.68),   # Frankfurt am Main
    "65": (50.08, 8.24),   # Wiesbaden
    "70": (48.78, 9.18),   # Stuttgart
    "76": (49.01, 8.40),   # Karlsruhe
    "80": (48.14, 11.58),  # Muenchen
    "85": (48.76, 11.43),  # Ingolstadt
    "90": (49.45, 11.08),  # Nuernberg
    "99": (50.98, 11.03),  # Erfurt
}

# One digit zones, as a fallback centroid for postal codes outside the table.
PLZ1_CENTROIDS: dict[str, tuple[float, float]] = {
    "0": (51.10, 13.20),
    "1": (52.45, 13.30),
    "2": (53.30, 9.70),
    "3": (51.60, 9.50),
    "4": (51.40, 7.20),
    "5": (50.90, 7.00),
    "6": (50.00, 8.60),
    "7": (48.80, 9.10),
    "8": (48.40, 11.40),
    "9": (49.60, 11.20),
}

EARTH_RADIUS_KM = 6371.0


def _centroid(plz: str) -> tuple[float, float] | None:
    plz = (plz or "").strip()
    if len(plz) < 1 or not plz[:1].isdigit():
        return None
    if len(plz) >= 2 and plz[:2] in PLZ2_CENTROIDS:
        return PLZ2_CENTROIDS[plz[:2]]
    return PLZ1_CENTROIDS.get(plz[:1])


def distance_km(plz_a: str, plz_b: str) -> float | None:
    """Great circle kilometres between two postal regions.

    Returns None when either code cannot be placed, so callers can treat unknown
    distance as unknown rather than as zero.
    """
    a, b = _centroid(plz_a), _centroid(plz_b)
    if a is None or b is None:
        return None
    if (plz_a or "")[:2] == (plz_b or "")[:2]:
        return 0.0
    lat1, lon1, lat2, lon2 = map(radians, (a[0], a[1], b[0], b[1]))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return round(2 * EARTH_RADIUS_KM * asin(sqrt(h)), 1)
