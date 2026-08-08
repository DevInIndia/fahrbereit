"""Vocabulary for the generated marketplace.

Manufacturer and model names are factual references to real vehicles, which is
permitted. Every dealer and rental operator name is invented, which is required.
Umlauts are transliterated, ae oe ue ss, to match the rest of the dataset.
"""

from __future__ import annotations

# Category to segment physics. One entry drives mass, boot, seats, power,
# displacement and the price band, so a generated car cannot be internally absurd.
SEGMENT: dict[str, dict] = {
    "Kleinstwagen": dict(
        basispreis=14_500, kw=(37, 66), masse=(880, 1_080), kofferraum=(170, 260),
        sitze=(4, 4), hubraum=(999, 1_242), verbrauch=(4.2, 5.6), kwh=(13.5, 16.0),
    ),
    "Kleinwagen": dict(
        basispreis=19_000, kw=(51, 96), masse=(1_020, 1_260), kofferraum=(260, 380),
        sitze=(5, 5), hubraum=(999, 1_498), verbrauch=(4.5, 6.2), kwh=(14.5, 17.5),
    ),
    "Kompaktklasse": dict(
        basispreis=26_000, kw=(81, 140), masse=(1_220, 1_520), kofferraum=(340, 450),
        sitze=(5, 5), hubraum=(1_197, 1_998), verbrauch=(4.8, 6.8), kwh=(15.0, 18.5),
    ),
    "Mittelklasse": dict(
        basispreis=36_000, kw=(110, 190), masse=(1_420, 1_720), kofferraum=(430, 530),
        sitze=(5, 5), hubraum=(1_497, 2_198), verbrauch=(5.2, 7.6), kwh=(16.0, 19.5),
    ),
    "Obere Mittelklasse": dict(
        basispreis=52_000, kw=(140, 250), masse=(1_600, 1_950), kofferraum=(480, 570),
        sitze=(5, 5), hubraum=(1_798, 2_998), verbrauch=(5.8, 8.6), kwh=(17.0, 21.0),
    ),
    "Oberklasse": dict(
        basispreis=88_000, kw=(190, 350), masse=(1_850, 2_300), kofferraum=(500, 620),
        sitze=(5, 5), hubraum=(2_497, 3_996), verbrauch=(6.8, 10.5), kwh=(18.5, 23.0),
    ),
    "SUV/Gelaendewagen": dict(
        basispreis=38_000, kw=(96, 220), masse=(1_450, 2_100), kofferraum=(430, 640),
        sitze=(5, 7), hubraum=(1_332, 2_498), verbrauch=(5.8, 8.8), kwh=(17.5, 21.5),
    ),
    "Kombi": dict(
        basispreis=32_000, kw=(90, 190), masse=(1_320, 1_750), kofferraum=(500, 690),
        sitze=(5, 5), hubraum=(1_197, 2_198), verbrauch=(4.8, 7.4), kwh=(16.0, 19.5),
    ),
    "Van/Grossraumlimousine": dict(
        basispreis=34_000, kw=(81, 160), masse=(1_450, 2_250), kofferraum=(600, 1_100),
        sitze=(5, 8), hubraum=(1_332, 2_143), verbrauch=(5.4, 8.2), kwh=(18.0, 22.0),
    ),
    "Sportwagen/Cabrio": dict(
        basispreis=46_000, kw=(97, 290), masse=(1_000, 1_700), kofferraum=(120, 320),
        sitze=(2, 4), hubraum=(1_496, 3_996), verbrauch=(6.0, 10.8), kwh=(17.0, 20.5),
    ),
}

# Price positioning by brand. Volume brands near one, premium above.
MARKE_NIVEAU: dict[str, float] = {
    "Dacia": 0.78, "Fiat": 0.88, "Suzuki": 0.88, "Mitsubishi": 0.88, "Citroen": 0.90,
    "Renault": 0.92, "Peugeot": 0.94, "Opel": 0.94, "Seat": 0.95, "Skoda": 0.98,
    "Ford": 0.96, "Kia": 0.97, "Hyundai": 0.97, "Nissan": 0.96, "Mazda": 1.00,
    "Toyota": 1.02, "Honda": 1.02, "Volkswagen": 1.06, "Smart": 1.02, "Cupra": 1.08,
    "Mini": 1.14, "Alfa Romeo": 1.12, "Jeep": 1.08, "Volvo": 1.20, "Tesla": 1.22,
    "Audi": 1.30, "BMW": 1.32, "Mercedes-Benz": 1.34, "Lexus": 1.28, "Jaguar": 1.30,
    "Land Rover": 1.34, "Genesis": 1.24, "Porsche": 1.65, "Maserati": 1.70,
    "Chevrolet": 1.05,
}

# At least ten distinct brands in every category, which is a graded requirement.
MODELLE: dict[str, list[tuple[str, str]]] = {
    "Kleinstwagen": [
        ("Fiat", "500"), ("Toyota", "Aygo X"), ("Kia", "Picanto"), ("Hyundai", "i10"),
        ("Volkswagen", "up!"), ("Skoda", "Citigo"), ("Seat", "Mii"), ("Renault", "Twingo"),
        ("Suzuki", "Ignis"), ("Mitsubishi", "Space Star"), ("Smart", "fortwo"),
        ("Citroen", "C1"),
    ],
    "Kleinwagen": [
        ("Volkswagen", "Polo"), ("Opel", "Corsa"), ("Ford", "Fiesta"), ("Renault", "Clio"),
        ("Peugeot", "208"), ("Citroen", "C3"), ("Skoda", "Fabia"), ("Seat", "Ibiza"),
        ("Toyota", "Yaris"), ("Mazda", "2"), ("Hyundai", "i20"), ("Kia", "Rio"),
        ("Nissan", "Micra"), ("Dacia", "Sandero"), ("Renault", "Zoe"),
    ],
    "Kompaktklasse": [
        ("Volkswagen", "Golf"), ("Opel", "Astra"), ("Ford", "Focus"), ("Skoda", "Octavia"),
        ("Seat", "Leon"), ("Renault", "Megane"), ("Peugeot", "308"), ("Toyota", "Corolla"),
        ("Mazda", "3"), ("Hyundai", "i30"), ("Kia", "Ceed"), ("Honda", "Civic"),
        ("BMW", "118i"), ("Mercedes-Benz", "A 180"), ("Audi", "A3"), ("Cupra", "Leon"),
        ("Volkswagen", "ID.3"),
    ],
    "Mittelklasse": [
        ("Volkswagen", "Passat"), ("Skoda", "Superb"), ("Ford", "Mondeo"),
        ("Opel", "Insignia"), ("Mazda", "6"), ("Toyota", "Camry"), ("Hyundai", "Sonata"),
        ("Kia", "Optima"), ("BMW", "320i"), ("Mercedes-Benz", "C 200"), ("Audi", "A4"),
        ("Volvo", "S60"), ("Peugeot", "508"), ("Tesla", "Model 3"),
    ],
    "Obere Mittelklasse": [
        ("BMW", "530i"), ("Mercedes-Benz", "E 220 d"), ("Audi", "A6"), ("Volvo", "S90"),
        ("Volkswagen", "Arteon"), ("Jaguar", "XF"), ("Lexus", "ES 300h"),
        ("Alfa Romeo", "Giulia"), ("Skoda", "Superb L&K"), ("Peugeot", "508 GT"),
        ("Opel", "Insignia GSi"), ("Genesis", "G70"),
    ],
    "Oberklasse": [
        ("BMW", "730d"), ("Mercedes-Benz", "S 400 d"), ("Audi", "A8 50 TDI"),
        ("Porsche", "Panamera 4"), ("Jaguar", "XJ"), ("Lexus", "LS 500h"),
        ("Tesla", "Model S"), ("Maserati", "Quattroporte"), ("Genesis", "G90"),
        ("Volvo", "S90 Excellence"),
    ],
    "SUV/Gelaendewagen": [
        ("Volkswagen", "Tiguan"), ("Skoda", "Kodiaq"), ("Seat", "Ateca"), ("Ford", "Kuga"),
        ("Opel", "Grandland"), ("Renault", "Kadjar"), ("Peugeot", "3008"),
        ("Toyota", "RAV4"), ("Mazda", "CX-5"), ("Hyundai", "Tucson"), ("Kia", "Sportage"),
        ("Nissan", "Qashqai"), ("BMW", "X3"), ("Mercedes-Benz", "GLC"), ("Audi", "Q5"),
        ("Dacia", "Duster"), ("Jeep", "Compass"), ("Land Rover", "Discovery Sport"),
        ("Volvo", "XC60"), ("Kia", "EV6"),
    ],
    "Kombi": [
        ("Volkswagen", "Passat Variant"), ("Skoda", "Octavia Combi"),
        ("Ford", "Focus Turnier"), ("Opel", "Astra Sports Tourer"),
        ("Seat", "Leon Sportstourer"), ("Renault", "Megane Grandtour"),
        ("Peugeot", "308 SW"), ("Toyota", "Corolla Touring Sports"), ("Mazda", "6 Kombi"),
        ("Hyundai", "i30 Kombi"), ("Kia", "Ceed SW"), ("BMW", "320d Touring"),
        ("Mercedes-Benz", "C 200 T"), ("Audi", "A4 Avant"), ("Volvo", "V60"),
    ],
    "Van/Grossraumlimousine": [
        ("Volkswagen", "Touran"), ("Ford", "S-Max"), ("Opel", "Zafira"),
        ("Renault", "Espace"), ("Citroen", "Berlingo"), ("Peugeot", "Rifter"),
        ("Seat", "Alhambra"), ("Toyota", "Proace Verso"), ("Mercedes-Benz", "V-Klasse"),
        ("Kia", "Carnival"), ("Hyundai", "Staria"), ("Dacia", "Jogger"),
        ("Fiat", "Doblo"), ("Volkswagen", "Caddy"),
    ],
    "Sportwagen/Cabrio": [
        ("Mazda", "MX-5"), ("Porsche", "718 Cayman"), ("BMW", "Z4"),
        ("Mercedes-Benz", "SLC"), ("Audi", "TT"), ("Volkswagen", "T-Roc Cabriolet"),
        ("Mini", "Cooper Cabrio"), ("Ford", "Mustang"), ("Toyota", "GR86"),
        ("Fiat", "124 Spider"), ("Nissan", "370Z"), ("Jaguar", "F-Type"),
        ("Alfa Romeo", "4C"), ("Chevrolet", "Camaro"),
    ],
}

# Models sold only as battery electric. Keeps a combustion Zoe out of the dataset.
NUR_ELEKTRO: set[tuple[str, str]] = {
    ("Renault", "Zoe"), ("Volkswagen", "ID.3"), ("Tesla", "Model 3"),
    ("Tesla", "Model S"), ("Kia", "EV6"),
}

# Trim levels, cheapest first. Position drives the equipment price multiplier.
AUSSTATTUNG: list[str] = ["Basis", "Trend", "Life", "Style", "Elegance", "Sport"]

# Invented dealer names. No real dealership group appears here.
HAENDLER_PRAEFIX = [
    "Autohaus", "Automobile", "Fahrzeugzentrum", "Motorhaus", "Kraftfahrzeuge",
]
HAENDLER_NAME = [
    "Lindmann", "Kerscher", "Rheinpark", "Nordstern", "Suedwerk", "Elbtal",
    "Weserhof", "Falkenberg", "Moorwiese", "Steinbach", "Hohenfeld", "Lichtenau",
    "Birkenhof", "Sandkrug", "Talblick", "Rosental", "Ankerplatz", "Wiesengrund",
]

# Invented rental operators. No real rental company appears here.
VERMIETER = [
    "Vogelsang Mobil", "Kranich Autovermietung", "Elbtal Mietwagen",
    "Nordlicht Fahrzeugmiete", "Baumgarten Fahrdienste", "Silberdistel Leihwagen",
    "Hafenkante Autovermietung", "Wegwarte Mietwagen",
]

# Real operator names that must never appear. Asserted by test.
VERBOTENE_NAMEN = [
    "Sixt", "Europcar", "Hertz", "Avis", "Enterprise", "Buchbinder", "Starcar",
    "Mobility", "Alamo", "Budget", "Sunny Cars", "AutoScout24", "mobile.de",
]

# Postal code, place. Spread across Germany so distance scoring has range.
ORTE: list[tuple[str, str]] = [
    ("10115", "Berlin"), ("12043", "Berlin"), ("20095", "Hamburg"),
    ("22767", "Hamburg"), ("80339", "Muenchen"), ("85049", "Ingolstadt"),
    ("50667", "Koeln"), ("53111", "Bonn"), ("60313", "Frankfurt am Main"),
    ("65183", "Wiesbaden"), ("70173", "Stuttgart"), ("76133", "Karlsruhe"),
    ("01067", "Dresden"), ("04109", "Leipzig"), ("28195", "Bremen"),
    ("30159", "Hannover"), ("40213", "Duesseldorf"), ("44135", "Dortmund"),
    ("90402", "Nuernberg"), ("99084", "Erfurt"),
]

# ACRISS, the four letter rental classification. Category, type, transmission and
# drive, fuel and air conditioning.
ACRISS_KATEGORIE: dict[str, str] = {
    "Kleinstwagen": "M", "Kleinwagen": "E", "Kompaktklasse": "C",
    "Mittelklasse": "I", "Obere Mittelklasse": "S", "Oberklasse": "L",
    "SUV/Gelaendewagen": "I", "Kombi": "S", "Van/Grossraumlimousine": "F",
    "Sportwagen/Cabrio": "S",
}
ACRISS_TYP: dict[str, str] = {
    "Kleinstwagen": "B", "Kleinwagen": "D", "Kompaktklasse": "D",
    "Mittelklasse": "D", "Obere Mittelklasse": "D", "Oberklasse": "L",
    "SUV/Gelaendewagen": "F", "Kombi": "W", "Van/Grossraumlimousine": "V",
    "Sportwagen/Cabrio": "T",
}
ACRISS_ANTRIEB: dict[str, str] = {"Schaltgetriebe": "M", "Automatik": "A"}
ACRISS_KRAFTSTOFF: dict[str, str] = {
    "Benzin": "R", "Diesel": "D", "Elektro": "E", "Hybrid": "H", "Plug-in-Hybrid": "H",
}


def acriss_code(kategorie: str, getriebe: str, kraftstoff: str) -> str:
    return (
        ACRISS_KATEGORIE[kategorie]
        + ACRISS_TYP[kategorie]
        + ACRISS_ANTRIEB[getriebe]
        + ACRISS_KRAFTSTOFF[kraftstoff]
    )
