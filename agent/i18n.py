"""German and English, switchable at request time.

The product is German market facing and the German vocabulary is the real one, so
German stays the default. English exists because a reader who does not speak German
should still be able to audit the ranking, which is the whole point of building it
transparently.

What is translated: every label, heading, explanation and unit phrase.

What is never translated, in either direction:

  - manufacturer, model and variant names (Volkswagen Golf 1.5 TSI Life)
  - dealer and rental operator names (Autohaus Steinbach)
  - place names and postal codes (München, 85049)
  - listing identifiers and ACRISS codes (FB-00228, CDMR)
  - the token SIMULATION, which must read identically everywhere

German segment names get an English gloss rather than a replacement, because
"Kompaktklasse" is the term a German listing actually uses and a reader should be
able to match what they see here against a real marketplace.

Number formatting follows the language: 14.670,50 in German, 14,670.50 in English.
"""

from __future__ import annotations

from typing import Literal

Lang = Literal["de", "en"]
DEFAULT_LANG: Lang = "de"
LANGS: tuple[Lang, ...] = ("de", "en")


def normalise(lang: str | None) -> Lang:
    value = (lang or "").strip().lower()[:2]
    return value if value in LANGS else DEFAULT_LANG  # type: ignore[return-value]


# ------------------------------------------------------------------ formatting


def fmt_int(value: float | int, lang: Lang = DEFAULT_LANG) -> str:
    """Thousands separators, per language. Tabular figures do the aligning."""
    raw = f"{int(round(value)):,}"
    return raw.replace(",", ".") if lang == "de" else raw


def fmt_dec(value: float, lang: Lang = DEFAULT_LANG, places: int = 1) -> str:
    raw = f"{value:,.{places}f}"
    if lang == "de":
        return raw.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return raw


def fmt_money(value: float | int, lang: Lang = DEFAULT_LANG) -> str:
    return f"{fmt_int(value, lang)} EUR"


# ------------------------------------------------------------------ vocabulary

# Segment names keep their German form and gain a gloss, so a reader can match what
# they see here against a real German marketplace listing.
KATEGORIE_GLOSS: dict[str, str] = {
    "Kleinstwagen": "city car",
    "Kleinwagen": "supermini",
    "Kompaktklasse": "compact",
    "Mittelklasse": "mid-size",
    "Obere Mittelklasse": "executive",
    "Oberklasse": "luxury",
    "SUV/Geländewagen": "SUV",
    "Kombi": "estate",
    "Van/Großraumlimousine": "MPV",
    "Sportwagen/Cabrio": "sports and convertible",
}

KRAFTSTOFF: dict[str, str] = {
    "Benzin": "petrol",
    "Diesel": "diesel",
    "Elektro": "electric",
    "Hybrid": "hybrid",
    "Plug-in-Hybrid": "plug-in hybrid",
}

GETRIEBE: dict[str, str] = {
    "Schaltgetriebe": "manual",
    "Automatik": "automatic",
}

PLAKETTE: dict[str, str] = {"grün": "green", "gelb": "yellow", "rot": "red"}


def kategorie(name: str, lang: Lang = DEFAULT_LANG) -> str:
    """German segment name, with an English gloss appended rather than replaced."""
    if lang == "de":
        return name
    gloss = KATEGORIE_GLOSS.get(name)
    return f"{name} ({gloss})" if gloss else name


def kraftstoff(name: str, lang: Lang = DEFAULT_LANG) -> str:
    return name if lang == "de" else KRAFTSTOFF.get(name, name)


def getriebe(name: str, lang: Lang = DEFAULT_LANG) -> str:
    return name if lang == "de" else GETRIEBE.get(name, name)


def plakette(name: str, lang: Lang = DEFAULT_LANG) -> str:
    return name if lang == "de" else PLAKETTE.get(name, name)


# ------------------------------------------------------------------ strings

STRINGS: dict[str, dict[str, str]] = {
    # headings and chrome
    "empfehlungen": {"de": "Empfehlungen", "en": "Recommendations"},
    "harte_filter": {"de": "Harte Filter", "en": "Hard filters"},
    "geprueft": {"de": "Geprüfte Angebote", "en": "Listings checked"},
    "ausgeschlossen": {"de": "ausgeschlossen", "en": "excluded"},
    "verblieben": {"de": "Verblieben", "en": "Remaining"},
    "gewichtung": {"de": "Gewichtung aus dem Interview", "en": "Weighting from the interview"},
    "warum": {"de": "Warum dieses Auto", "en": "Why this car"},
    "dimension": {"de": "Dimension", "en": "Dimension"},
    "gewicht": {"de": "Gewicht", "en": "Weight"},
    "rang": {"de": "Rang", "en": "Rank"},
    "beitrag": {"de": "Beitrag", "en": "Contribution"},
    "begruendung": {"de": "Begründung", "en": "Basis"},
    "gesamt": {"de": "Gesamt", "en": "Total"},
    "zusammengesetzt": {
        "de": "Zusammengesetzte Dimensionen",
        "en": "Composite dimensions",
    },
    "ausschlaggebend": {"de": "Ausschlaggebend", "en": "Decisive factors"},
    "schwaechen": {"de": "Schwächen", "en": "Weaknesses"},
    "gegen_platz_2": {"de": "Gegen Platz 2", "en": "Against runner-up"},
    "interview": {"de": "Interview", "en": "Interview"},
    "persona": {"de": "Persona", "en": "Persona"},
    "ablauf": {"de": "Ablauf", "en": "Flow"},
    "katalog": {"de": "Katalog", "en": "Catalogue"},
    "formular": {"de": "Formular", "en": "Form"},
    "kasse": {"de": "Kasse", "en": "Checkout"},
    "offen": {"de": "offen", "en": "open"},
    "gesagt": {"de": "gesagt", "en": "stated"},
    "abgeleitet": {"de": "abgeleitet", "en": "inferred"},
    "bridge_protokoll": {"de": "Bridge-Protokoll", "en": "Bridge log"},
    "zuruecksetzen": {"de": "zurücksetzen", "en": "reset"},
    "nur": {"de": "nur", "en": "only"},
    "sprache": {"de": "Sprache", "en": "Language"},
    "wird_aufgebaut": {
        "de": "Oberfläche wird aufgebaut...",
        "en": "Building the surface...",
    },
    "wird_geladen": {"de": "Wird geladen...", "en": "Loading..."},
    "backend_weg": {
        "de": "Backend nicht erreichbar",
        "en": "Backend unreachable",
    },
    "konnte_nicht_laden": {
        "de": "Konnte die Oberfläche nicht laden",
        "en": "Could not load the surface",
    },
    # dimension labels
    "dim.preis_spielraum": {"de": "Preisspielraum", "en": "Price headroom"},
    "dim.gesamtkosten": {"de": "Gesamtkosten", "en": "Total cost"},
    "dim.alter_laufleistung": {"de": "Alter und Laufleistung", "en": "Age and mileage"},
    "dim.einsatzzweck": {"de": "Einsatzzweck", "en": "Fitness for purpose"},
    "dim.zustand": {"de": "Zustand", "en": "Condition"},
    "dim.entfernung": {"de": "Entfernung", "en": "Distance"},
    # hard constraint labels
    "c.angebotsart": {"de": "Angebotsart", "en": "Listing type"},
    "c.kategorie": {"de": "Fahrzeugkategorie", "en": "Vehicle category"},
    "c.budget": {"de": "Budget", "en": "Budget"},
    "c.getriebe": {"de": "Getriebe", "en": "Transmission"},
    "c.kraftstoff": {"de": "Kraftstoff", "en": "Fuel"},
    "c.sitzplaetze": {"de": "Sitzplätze", "en": "Seats"},
    "c.kofferraum": {"de": "Kofferraumvolumen", "en": "Boot volume"},
    "c.umweltplakette": {"de": "Umweltplakette", "en": "Emissions badge"},
    "c.kilometerstand": {"de": "Kilometerstand", "en": "Mileage"},
    "c.unfallfrei": {"de": "Unfallfreiheit", "en": "Accident-free"},
    "c.entfernung": {"de": "Entfernung", "en": "Distance"},
    # composite component names
    "k.Sitzplätze": {"de": "Sitzplätze", "en": "Seats"},
    "k.Kofferraum": {"de": "Kofferraum", "en": "Boot"},
    "k.Ladevolumen": {"de": "Ladevolumen", "en": "Load volume"},
    "k.Stadttauglichkeit": {"de": "Stadttauglichkeit", "en": "City suitability"},
    "k.Verbrauch": {"de": "Verbrauch", "en": "Consumption"},
    "k.Motorisierung": {"de": "Motorisierung", "en": "Engine output"},
    "k.Vorsteuerabzug": {"de": "Vorsteuerabzug", "en": "VAT deductible"},
    "k.Unfallfreiheit": {"de": "Unfallfreiheit", "en": "Accident-free"},
    "k.Vorbesitzer": {"de": "Vorbesitzer", "en": "Previous owners"},
    "k.HU": {"de": "HU", "en": "Roadworthiness test"},
    # cost of ownership line items
    "t.kfz_steuer": {"de": "Kfz-Steuer", "en": "Vehicle tax"},
    "t.versicherung": {"de": "Versicherung", "en": "Insurance"},
    "t.energie": {"de": "Energie", "en": "Energy"},
    "t.wartung": {"de": "Wartung", "en": "Maintenance"},
    "t.wertverlust": {"de": "Wertverlust", "en": "Depreciation"},
    "t.restwert": {"de": "Restwert", "en": "Residual value"},
    # checkout
    "kasse.rechnungsposten": {"de": "Rechnungsposten", "en": "Invoice items"},
    "kasse.position": {"de": "Position", "en": "Item"},
    "kasse.menge": {"de": "Menge", "en": "Qty"},
    "kasse.netto": {"de": "Nettobetrag", "en": "Net amount"},
    "kasse.mwst": {"de": "zzgl. 19 % MwSt.", "en": "plus 19 % VAT"},
    "kasse.brutto": {"de": "Gesamtbetrag", "en": "Total amount"},
    "kasse.zahlung": {
        "de": "Zahlung per SEPA-Überweisung, simuliert",
        "en": "Payment by SEPA transfer, simulated",
    },
    "kasse.empfaenger": {"de": "Empfänger", "en": "Payee"},
    "kasse.abholung": {"de": "Abholung", "en": "Collection"},
    "kasse.station": {"de": "Station", "en": "Location"},
    "kasse.zeitraum": {"de": "Zeitraum", "en": "Period"},
    "kasse.kaution": {"de": "Kaution, erstattbar", "en": "Deposit, refundable"},
    "kasse.kaufvertrag": {"de": "Kaufvertrag", "en": "Purchase contract"},
    "kasse.mietvertrag": {"de": "Mietvertrag", "en": "Rental contract"},
    "kasse.simulieren": {"de": "simulieren", "en": "simulate"},
    # Full phrases, because German puts the verb last and a concatenation that reads
    # correctly in one language reads as broken in the other.
    "kasse.btn_kauf": {
        "de": "Kaufvertrag simulieren", "en": "Simulate purchase contract",
    },
    "kasse.btn_miete": {
        "de": "Mietvertrag simulieren", "en": "Simulate rental contract",
    },
    "kasse.bestaetigung": {"de": "Bestätigung", "en": "Confirmation"},
    "kasse.vertrag_ref": {"de": "Vertragsreferenz", "en": "Contract reference"},
    "kasse.zahl_ref": {"de": "Zahlungsreferenz", "en": "Payment reference"},
    "kasse.status": {"de": "Status", "en": "Status"},
    "kasse.simuliert_suffix": {"de": "simuliert", "en": "simulated"},
    "kasse.banner": {
        "de": "Dies ist eine Vorführung. Es wird kein Geld bewegt, keine Bank "
              "kontaktiert und kein Vertrag geschlossen.",
        "en": "This is a demonstration. No money moves, no bank is contacted and no "
              "contract is concluded.",
    },
    "kasse.iban_hinweis": {
        "de": "Die IBAN ist absichtlich ungültig. Die Prüfziffer 00 kann in keiner "
              "echten IBAN vorkommen. Es existiert in dieser Anwendung kein Feld "
              "für Kartendaten.",
        "en": "The IBAN is deliberately invalid. Check digits of 00 can never occur in "
              "a real IBAN. This application contains no field for card details "
              "anywhere.",
    },
    "kasse.verarbeitet": {
        "de": "Simulierte Zahlung wird verarbeitet...",
        "en": "Processing the simulated payment...",
    },
    "kasse.fertig": {
        "de": "Simulation abgeschlossen. Es wurde kein Geld bewegt.",
        "en": "Simulation complete. No money moved.",
    },
    "kasse.fehlgeschlagen": {
        "de": "Simulierte Zahlung fehlgeschlagen.",
        "en": "Simulated payment failed.",
    },
    # form
    "form.kaufanfrage": {"de": "Kaufanfrage", "en": "Purchase enquiry"},
    "form.mietanfrage": {"de": "Mietanfrage", "en": "Rental enquiry"},
    "form.angebot": {"de": "Angebot", "en": "Listing"},
    "form.name": {"de": "Name", "en": "Name"},
    "form.name_ph": {"de": "Vor- und Nachname", "en": "First and last name"},
    "form.email": {"de": "E-Mail", "en": "Email"},
    "form.zahlungsart": {"de": "Zahlungsart", "en": "Payment method"},
    "form.barzahlung": {"de": "Barzahlung", "en": "Cash"},
    "form.finanzierung": {"de": "Finanzierung", "en": "Financing"},
    "form.fs_seit": {"de": "Führerschein seit", "en": "Licence held since"},
    "form.versicherung": {"de": "Versicherungsschutz", "en": "Insurance cover"},
    "form.basis": {"de": "Basis", "en": "Basic"},
    "form.komfort": {"de": "Komfort", "en": "Comfort"},
    "form.premium": {"de": "Premium", "en": "Premium"},
    "form.weiter": {"de": "Weiter zur Kasse", "en": "Continue to checkout"},
    "form.pflichtfeld": {"de": "Pflichtfeld", "en": "Required"},
    "form.email_ungueltig": {
        "de": "Bitte eine gültige E-Mail-Adresse angeben",
        "en": "Please enter a valid email address",
    },
    "form.jahr_zwischen": {"de": "Jahr zwischen 1950 und", "en": "Year between 1950 and"},
    "form.pruefen": {
        "de": "Bitte die markierten Felder prüfen.",
        "en": "Please check the highlighted fields.",
    },
    "form.uebernommen": {
        "de": "Übernommen. Die Unterhaltung geht weiter.",
        "en": "Saved. The conversation continues.",
    },
    "form.wird_uebernommen": {"de": "Wird übernommen...", "en": "Saving..."},
    "form.fussnote": {
        "de": "Ihre Angaben bleiben in dieser Unterhaltung. Es findet keine Weitergabe "
              "statt, und es wird keine echte Buchung ausgelöst.",
        "en": "Your details stay in this conversation. Nothing is shared onward and no "
              "real booking is made.",
    },
    # Interview slot names. These are internal field names and must never reach a
    # user untranslated, in either language.
    "slot.intent": {"de": "Absicht", "en": "Intent"},
    "slot.use_case_text": {"de": "Beschreibung", "en": "Description"},
    "slot.use_case_tags": {"de": "Einsatzzweck", "en": "Use case"},
    "slot.category_preference": {"de": "Fahrzeugkategorie", "en": "Vehicle category"},
    "slot.budget": {"de": "Budget", "en": "Budget"},
    "slot.target_date": {"de": "Wunschtermin", "en": "Target date"},
    "slot.date_flexibility_days": {"de": "Terminspielraum", "en": "Date flexibility"},
    "slot.jahresfahrleistung_km": {"de": "Jahresfahrleistung", "en": "Annual mileage"},
    "slot.constraints_hard": {"de": "Harte Kriterien", "en": "Hard criteria"},
    "slot.preferences_soft": {"de": "Gewichtung", "en": "Weighting"},
    "slot.location": {"de": "Standort", "en": "Location"},
    # Values inside those slots.
    "intent.kauf": {"de": "kaufen", "en": "buy"},
    "intent.miete": {"de": "mieten", "en": "rent"},
    "intent.unentschieden": {"de": "unentschieden", "en": "undecided"},
    "tag.pendeln": {"de": "Pendeln", "en": "commuting"},
    "tag.familie": {"de": "Familie", "en": "family"},
    "tag.stadtverkehr": {"de": "Stadtverkehr", "en": "city driving"},
    "tag.langstrecke": {"de": "Langstrecke", "en": "long distance"},
    "tag.umzug": {"de": "Umzug", "en": "moving house"},
    "tag.wochenende": {"de": "Wochenende", "en": "weekends"},
    "tag.gewerblich": {"de": "Gewerblich", "en": "business use"},
    # Field names inside the composite slots.
    "f.max_kaufpreis_eur": {"de": "max. Kaufpreis", "en": "max. price"},
    "f.max_monatsrate_eur": {"de": "max. Monatsrate", "en": "max. monthly"},
    "f.max_tagessatz_eur": {"de": "max. Tagessatz", "en": "max. daily rate"},
    "f.max_gesamtmiete_eur": {"de": "max. Gesamtmiete", "en": "max. total rental"},
    "f.getriebe": {"de": "Getriebe", "en": "transmission"},
    "f.kraftstoff": {"de": "Kraftstoff", "en": "fuel"},
    "f.min_sitzplaetze": {"de": "min. Sitzplätze", "en": "min. seats"},
    "f.min_kofferraum_liter": {"de": "min. Kofferraum", "en": "min. boot"},
    "f.umweltplakette": {"de": "Umweltplakette", "en": "emissions badge"},
    "f.max_kilometerstand": {"de": "max. Kilometerstand", "en": "max. mileage"},
    "f.unfallfrei_erforderlich": {"de": "unfallfrei", "en": "accident-free"},
    "f.max_entfernung_km": {"de": "max. Entfernung", "en": "max. distance"},
    "f.plz": {"de": "PLZ", "en": "postcode"},
    "f.ort": {"de": "Ort", "en": "place"},
    "ja": {"de": "ja", "en": "yes"},
    "fehler": {"de": "Fehler", "en": "Error"},
}


def t(key: str, lang: Lang = DEFAULT_LANG) -> str:
    entry = STRINGS.get(key)
    if entry is None:
        return key
    return entry.get(lang, entry.get(DEFAULT_LANG, key))
