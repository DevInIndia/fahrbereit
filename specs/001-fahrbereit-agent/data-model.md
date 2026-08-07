# Phase 1: Data model

**Feature**: 001-fahrbereit-agent | **Date**: 2026-08-07

All names that appear in the product vocabulary are German, matching the trade terms a
buyer would meet on a German marketplace. Field names in code follow the same vocabulary
so that a value can be traced from a listing file through a trace span to a rendered cell
without translation.

## 1. Interview state

### Provenance

Every slot is wrapped rather than stored bare, because the interface must distinguish what
the user said from what the agent worked out.

```
Slot[T]
  value:      T | None
  provenance: "stated" | "inferred" | "default" | None
  confidence: float          # 0.0 to 1.0, only meaningful when inferred
  confirmed:  bool           # the user was shown the inference and accepted it
  source:     str | None     # the utterance or rule the value came from
  updated_at: datetime
```

An inferred slot that has not been confirmed is rendered with a distinct mark and is a
candidate for a confirmation question. A stated slot is never overwritten by inference.

### Slots

| Slot | Type | Notes |
|---|---|---|
| `intent` | `kauf \| miete \| unentschieden` | Governs which budget semantics and which form apply. |
| `use_case_text` | `str` | The user's own words, retained verbatim for the narration. |
| `use_case_tags` | `set[UseCaseTag]` | Derived. `pendeln`, `familie`, `stadtverkehr`, `langstrecke`, `umzug`, `wochenende`, `gewerblich`. |
| `category_preference` | `list[Kategorie]` | Stated, or inferred from tags when absent. |
| `budget` | `Budget` | See below. |
| `target_date` | `date` | Purchase or collection date. |
| `date_flexibility_days` | `int` | Window either side of the target. |
| `jahresfahrleistung_km` | `int` | Annual mileage. Drives the energy term of cost of ownership. |
| `constraints_hard` | `HardConstraints` | See below. |
| `preferences_soft` | `dict[Dimension, float]` | Weights, summing to one after normalisation. |
| `location` | `Location` | Postal code, place name, maximum acceptable distance in kilometres. |

```
Budget
  # kauf
  max_kaufpreis_eur:      int | None
  max_monatsrate_eur:     int | None    # optional financing ceiling
  # miete
  max_tagessatz_eur:      int | None
  max_gesamtmiete_eur:    int | None

HardConstraints
  getriebe:               "Schaltgetriebe" | "Automatik" | None
  kraftstoff:             list[Kraftstoff] | None
  min_sitzplaetze:        int | None
  min_kofferraum_liter:   int | None
  umweltplakette:         "grün" | "gelb" | "rot" | None    # minimum acceptable
  max_kilometerstand:     int | None
  unfallfrei_erforderlich: bool
  max_entfernung_km:      int | None
  min_fahreralter_erfuellt: bool                            # rental only
```

### Phase

`interview -> suche -> bewertung -> empfehlung -> formular -> kasse -> abgeschlossen`

The phase advances only when the slots that phase requires are populated. It may move
backwards when the user revises, which is the mechanism the next section describes.

### Invalidation map

A revision invalidates the artifacts that read the revised slot, and nothing else. This is
the whole of the state machine's cleverness and it is deliberately a table rather than
logic.

| Revised slot | Invalidated |
|---|---|
| `intent` | filter report, ranking, selection, booking details, order |
| `budget` | filter report, ranking, selection |
| `constraints_hard.*` | filter report, ranking, selection |
| `location` | filter report, ranking, selection |
| `category_preference` | filter report, ranking, selection |
| `jahresfahrleistung_km` | cost of ownership, ranking (score only, filter survives) |
| `preferences_soft` | ranking (score and order only, filter survives) |
| `use_case_tags` | ranking (score only) |
| `target_date` | availability, ranking, order |
| `use_case_text` | nothing computed; narration only |

Two properties matter here. A weight change never re-runs the hard filter, which is what
makes in place re-ranking fast enough to feel like an instrument. A budget change never
discards the interview, which is what stops the agent from re-interrogating the user.

## 2. Listing

Fields common to both listing types:

| Field | Type | Note |
|---|---|---|
| `id` | `str` | `FB-00042` |
| `listing_type` | `kauf \| miete` | |
| `brand`, `model`, `variant` | `str` | Manufacturer names are factual references. |
| `category` | `Kategorie` | One of the ten segments. |
| `erstzulassung` | `str` | `YYYY-MM`, first registration. |
| `kilometerstand` | `int` | |
| `leistung_kw`, `leistung_ps` | `int` | Both, because both are quoted in German listings. |
| `hubraum_ccm` | `int` | Zero for battery electric. Required for motor vehicle tax. |
| `leermasse_kg` | `int` | Required for the weight based tax applied to electric cars. |
| `getriebe` | `Schaltgetriebe \| Automatik` | |
| `kraftstoff` | `Benzin \| Diesel \| Elektro \| Hybrid \| Plug-in-Hybrid` | |
| `verbrauch_l_100km` | `float \| None` | Combined, null for battery electric. |
| `verbrauch_kwh_100km` | `float \| None` | Null for combustion only. |
| `co2_g_km` | `int` | |
| `schadstoffklasse` | `str` | `Euro 6d` and similar. |
| `umweltplakette` | `grün \| gelb \| rot` | |
| `hu_faellig` | `str` | `YYYY-MM`, next roadworthiness inspection. |
| `vorbesitzer` | `int` | |
| `unfallfrei` | `bool` | |
| `sitzplaetze` | `int` | |
| `kofferraum_liter` | `int` | |
| `haendler` | `str` | Invented. |
| `standort_plz`, `standort_ort` | `str` | |

Purchase listings add `preis_eur` and `mwst_ausweisbar`. Rental listings add:

| Field | Type | Note |
|---|---|---|
| `acriss` | `str` | Four letters: category, type, transmission and drive, fuel and air conditioning. |
| `tagessatz_eur`, `wochensatz_eur` | `int` | |
| `mindestmietdauer_tage` | `int` | |
| `inklusiv_km_pro_tag` | `int` | |
| `mehrkilometer_eur` | `float` | Per excess kilometre. |
| `kaution_eur` | `int` | |
| `mindestalter` | `int` | |
| `verfuegbar_von`, `verfuegbar_bis` | `str` | ISO dates, checked before checkout. |

### Generation invariants

Asserted by test, not by inspection:

- at least two hundred and fifty listings; exactly ten categories; at least ten distinct
  brands in every category
- both listing types present in every category
- within one brand, model and variant, price falls monotonically as age and mileage rise
- power, displacement, consumption and emissions are mutually consistent and consistent
  with the segment
- environmental badge follows from emissions class; battery electric is always green
- no dealer or operator name appears on the reserved real world name list
- regenerating from the committed seed reproduces the committed file byte for byte

## 3. Cost of ownership

Five years, computed per listing against the user's annual mileage. Every term is a
published formula or a stated segment average, and each is displayed as its own line so
the total can be checked.

**Kfz-Steuer**, the German motor vehicle tax, annual:

- combustion: a displacement term, two euro per hundred cubic centimetres begun for petrol
  and nine euro fifty for diesel, plus an emissions term applied to the part of the carbon
  dioxide figure above a ninety five gram allowance. Cars first registered from January
  2021 use the tiered emissions rates; earlier registrations use the flat two euro per
  gram.
- battery electric: exempt where first registration falls inside the exemption window,
  otherwise a mass based rate reduced by half.

**Insurance**: an estimated annual band from segment, power and vehicle age. Presented as
an estimate with its band, never as a quotation.

**Energy**: annual mileage multiplied by consumption multiplied by a stated unit price,
per fuel type.

**Maintenance**: a segment base cost scaled by vehicle age, with a wear step once the
vehicle passes a mileage threshold.

**Residual value**: the purchase price depreciated over five further years on a declining
curve whose rate depends on segment and drivetrain, subtracted from the total as recovered
value.

The structure returned per listing is itemised, and the sum of the items equals the
reported total. That equality is a test.

## 4. Filter report and score

```
FilterReport
  gesamt:           int                  # dataset size considered
  uebrig:           int                  # survivors
  ausgeschlossen:   dict[str, int]       # constraint name to elimination count
```

The elimination counts are attributed to the first constraint each listing fails, in a
fixed order, so the counts sum to the number excluded and the report can be read aloud.

```
ScoreBreakdown
  dimensionen: list[DimensionScore]
  total:       float                     # 0 to 100

DimensionScore
  name:      Dimension
  gewicht:   float                       # normalised weight
  rohwert:   float                       # 0 to 100, the dimension's own scale
  beitrag:   float                       # gewicht * rohwert
  begruendung: str                       # the fact the raw value came from
```

Dimensions: `preis_spielraum`, `gesamtkosten`, `alter_laufleistung`, `einsatzzweck`,
`zustand`, `entfernung`. The sum of contributions equals the total, which is a test and a
displayed property.

```
Recommendation
  listing:      Listing
  score:        ScoreBreakdown
  tco:          CostOfOwnership
  rang:         int
  top_faktoren: list[str]                # the two or three largest contributions
  vergleich:    Comparison | None        # against the next ranked alternative
```

`Comparison` holds quantified deltas only, cost over five years, mileage, age, power, so
that the narration has facts to state and cannot invent any.

## 5. Booking and order

`BookingDetails` is a discriminated union on intent. Purchase carries buyer identity,
payment mode of cash or financing, trade in flag and collection date. Rental carries
driver identity, licence held since, rental window, additional driver flag and insurance
tier.

`Order` holds line items, net, tax at nineteen percent and gross totals, the contract
reference and the payment reference. Both references embed the token `SIMULATION`. The
bank identifier is a fixed, obviously invalid constant. There is no card field in this
model, which is the point.
