"""Scoring for the persona evaluations.

Three of the four measures are deterministic and none of those calls a model. That
split is the point of the design rather than an economy: whether a recommendation
violates a hard constraint is a fact about the listing, and asking a language model
to judge it would convert a checkable fact into an opinion with a confidence score
attached. The judge is used for exactly one thing, whether the narration is faithful
to the figures it was given, because that is genuinely a question about language.

Even faithfulness is checked deterministically first. Every number in the reply is
extracted and matched against the set of figures the agent was actually handed. A
number that appears nowhere in that set is a fabrication, and no judgement is needed
to say so. The judge then reads what the arithmetic cannot: whether the claims made
about those numbers are supported.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from pydantic import BaseModel

from agent.listing import PLAKETTEN_RANG, Listing
from agent.state import InterviewState
from agent.tools.geo import distance_km


class SlotScore(BaseModel):
    erwartet: int
    getroffen: int
    fehlend: list[str] = []
    falsch: list[str] = []

    @property
    def anteil(self) -> float:
        return self.getroffen / self.erwartet if self.erwartet else 1.0


class ConstraintScore(BaseModel):
    geprueft: int
    verstoesse: int
    details: list[str] = []
    erwartet_leer: bool = False
    leer_korrekt: Optional[bool] = None


class FaithfulnessScore(BaseModel):
    zahlen_im_text: int
    zahlen_belegt: int
    erfundene_zahlen: list[str] = []
    richter_punktzahl: Optional[float] = None
    richter_begruendung: str = ""

    @property
    def zahlen_anteil(self) -> float:
        return self.zahlen_belegt / self.zahlen_im_text if self.zahlen_im_text else 1.0


# ------------------------------------------------------------------ slot filling


def _resolve(state: InterviewState, path: str) -> tuple[bool, Any]:
    """Read a possibly dotted slot path. Returns (is_set, value)."""
    if "." in path:
        name, field = path.split(".", 1)
        slot = state.slot(name)
        if not slot.is_set:
            return False, None
        return True, getattr(slot.value, field, None)
    slot = state.slot(path)
    return slot.is_set, slot.value


def _same(expected: Any, actual: Any) -> bool:
    """Compare ground truth to what was recorded, tolerating harmless shape drift."""
    if actual is None:
        return False
    actual = getattr(actual, "value", actual)  # unwrap enums
    if isinstance(expected, list):
        got = {str(getattr(x, "value", x)) for x in (actual or [])}
        return {str(x) for x in expected}.issubset(got)
    if isinstance(expected, bool):
        return bool(actual) is expected
    if isinstance(expected, (int, float)):
        return isinstance(actual, (int, float)) and float(actual) == float(expected)
    return str(actual).strip().lower() == str(expected).strip().lower()


def score_slots(state: InterviewState, erwartet: dict[str, Any]) -> SlotScore:
    """How much of the ground truth interview the agent actually recorded.

    A slot expected with a null value counts as filled whatever the value is: some
    ground truth is "you should have worked out that this is a family" rather than a
    specific figure, and pinning the exact tag set would score wording, not behaviour.
    """
    treffer, fehlend, falsch = 0, [], []
    for path, wanted in erwartet.items():
        is_set, actual = _resolve(state, path)
        if not is_set or (wanted is None and actual is None):
            fehlend.append(path)
        elif wanted is None or _same(wanted, actual):
            treffer += 1
        else:
            falsch.append(f"{path}: wanted {wanted!r}, recorded {actual!r}")
    return SlotScore(
        erwartet=len(erwartet), getroffen=treffer, fehlend=fehlend, falsch=falsch
    )


# ------------------------------------------------------------------ hard constraints


def _violations(listing: Listing, kriterien: dict[str, Any]) -> list[str]:
    """Every hard criterion this listing breaks. Checked against the listing itself."""
    out: list[str] = []

    if (want := kriterien.get("listing_type")) and listing.listing_type != want:
        out.append(f"listing type {listing.listing_type} is not {want}")
    if (cap := kriterien.get("max_preis_eur")) is not None:
        if (listing.preis_eur or 0) > cap:
            out.append(f"price {listing.preis_eur} over {cap}")
    if (cap := kriterien.get("max_tagessatz_eur")) is not None:
        if (listing.tagessatz_eur or 0) > cap:
            out.append(f"daily rate {listing.tagessatz_eur} over {cap}")
    if (want := kriterien.get("getriebe")) and listing.getriebe != want:
        out.append(f"transmission {listing.getriebe} is not {want}")
    if (want := kriterien.get("kraftstoff")) and listing.kraftstoff not in want:
        out.append(f"fuel {listing.kraftstoff} not in {want}")
    if (need := kriterien.get("min_sitzplaetze")) and listing.sitzplaetze < need:
        out.append(f"{listing.sitzplaetze} seats under {need}")
    if (need := kriterien.get("min_kofferraum_liter")) and listing.kofferraum_liter < need:
        out.append(f"boot {listing.kofferraum_liter} l under {need} l")
    if want := kriterien.get("umweltplakette"):
        if PLAKETTEN_RANG.get(listing.umweltplakette, 0) < PLAKETTEN_RANG.get(want, 0):
            out.append(f"emissions badge {listing.umweltplakette} below {want}")
    if (cap := kriterien.get("max_kilometerstand")) and listing.kilometerstand > cap:
        out.append(f"mileage {listing.kilometerstand} over {cap}")
    if kriterien.get("unfallfrei") and not listing.unfallfrei:
        out.append("has accident damage")
    if (cap := kriterien.get("max_entfernung_km")) and (von := kriterien.get("von_plz")):
        d = distance_km(von, listing.standort_plz)
        if d is not None and d > cap:
            out.append(f"{d:.0f} km away, over the {cap} km radius")
    return out


def score_constraints(
    empfehlungen: list[Listing], kriterien: dict[str, Any]
) -> ConstraintScore:
    """SC-001 as an evaluation. Not one recommendation may break a hard criterion."""
    erwartet_leer = bool(kriterien.get("erwartet_leer"))
    details: list[str] = []
    verstoesse = 0
    for listing in empfehlungen:
        broken = _violations(listing, kriterien)
        if broken:
            verstoesse += 1
            details.append(f"{listing.id} {listing.bezeichnung}: {'; '.join(broken)}")

    return ConstraintScore(
        geprueft=len(empfehlungen),
        verstoesse=verstoesse,
        details=details[:5],
        erwartet_leer=erwartet_leer,
        leer_korrekt=(len(empfehlungen) == 0) if erwartet_leer else None,
    )


# ------------------------------------------------------------------ faithfulness

# Numbers as a reader meets them: 25.000, 25,000, 25000, 5,8, 5.8.
#
# The lookbehind matters more than it looks. Without it the digits inside a listing
# identifier, FB-00157, are read as the figure 157 and reported as a fabrication,
# which is a harness defect that would have been published as an agent failure.
ZAHL = re.compile(r"(?<![\w-])\d[\d.,]*")

# Small integers are ordinals, counts and list positions far more often than they are
# claims about data, and treating "the first two" as a fabricated figure would drown
# the real signal. The threshold is a judgement call and is stated rather than hidden.
KLEINZAHL_GRENZE = 100


def _normalise_number(raw: str) -> Optional[float]:
    text = raw.strip().rstrip(".,")
    if not text:
        return None
    if "," in text and "." in text:
        # German 25.000,50 or English 25,000.50, decided by which separator is last.
        text = (
            text.replace(".", "").replace(",", ".")
            if text.rfind(",") > text.rfind(".")
            else text.replace(",", "")
        )
    elif "," in text:
        parts = text.split(",")
        text = text.replace(",", ".") if len(parts[-1]) != 3 else text.replace(",", "")
    elif "." in text:
        parts = text.split(".")
        if len(parts[-1]) == 3 and len(parts) >= 2:
            text = text.replace(".", "")
    try:
        return float(text)
    except ValueError:
        return None


def numbers_in(text: str) -> list[tuple[str, float]]:
    out = []
    for match in ZAHL.finditer(text or ""):
        value = _normalise_number(match.group())
        if value is not None:
            out.append((match.group(), value))
    return out


def erlaubte_zahlen(ranking, state: Optional[InterviewState] = None) -> set[float]:
    """Every figure the agent was actually handed, so anything else is invented.

    Three sources, and leaving any of them out manufactures false positives that read
    as agent failures. The ranking result is the obvious one. The vehicle names are
    the second: a Fiat 500 and a Mercedes C 200 carry numbers that are part of a
    proper noun, not claims about data. The user's own stated requirements are the
    third: an advisor repeating "the 550 litres you asked for" is being faithful, and
    scoring that as invention would penalise exactly the behaviour we want.
    """
    allowed: set[float] = set()

    if state is not None:
        if (budget := state.budget.value) is not None:
            allowed.update(
                float(x)
                for x in (
                    budget.max_kaufpreis_eur, budget.max_tagessatz_eur,
                    budget.max_monatsrate_eur, budget.max_gesamtmiete_eur,
                )
                if x is not None
            )
        if (c := state.constraints_hard.value) is not None:
            allowed.update(
                float(x)
                for x in (
                    c.min_sitzplaetze, c.min_kofferraum_liter,
                    c.max_kilometerstand, c.max_entfernung_km,
                )
                if x is not None
            )
        if (loc := state.location.value) is not None:
            if loc.plz and loc.plz.isdigit():
                allowed.add(float(loc.plz))
            if loc.max_entfernung_km:
                allowed.add(float(loc.max_entfernung_km))
        for slot in (state.jahresfahrleistung_km, state.mietdauer_tage):
            if slot.value is not None:
                allowed.add(float(slot.value))

    if ranking is None:
        return allowed

    allowed.add(float(ranking.report.gesamt))
    allowed.add(float(ranking.report.uebrig))
    allowed.update(float(v) for v in ranking.report.ausgeschlossen.values())
    if ranking.report.angenommener_radius_km:
        allowed.add(float(ranking.report.angenommener_radius_km))

    for rec in ranking.empfehlungen:
        listing = rec.listing
        allowed.update(
            float(x)
            for x in (
                rec.rang, rec.score.total, rec.score.basis_anzahl,
                listing.kilometerstand, listing.leistung_kw, listing.leistung_ps,
                listing.sitzplaetze, listing.kofferraum_liter, listing.co2_g_km,
                listing.erstzulassung_jahr, listing.erstzulassung_monat,
                listing.hubraum_ccm, listing.leermasse_kg, listing.vorbesitzer,
            )
            if x is not None
        )
        for optional in (
            listing.preis_eur, listing.tagessatz_eur, listing.wochensatz_eur,
            listing.kaution_eur, listing.inklusiv_km_pro_tag, listing.mindestalter,
            listing.mindestmietdauer_tage, listing.verbrauch_l_100km,
            listing.verbrauch_kwh_100km, rec.tco_gesamt_eur,
        ):
            if optional is not None:
                allowed.add(float(optional))
        # The dealer's postcode is a figure the agent is given and may quote.
        if listing.standort_plz.isdigit():
            allowed.add(float(listing.standort_plz))
        # Numbers inside the vehicle's name are part of a proper noun: Fiat 500,
        # Mercedes C 200, Audi A4, Peugeot 208.
        for token in ZAHL.findall(listing.bezeichnung):
            if (value := _normalise_number(token)) is not None:
                allowed.add(value)
        for dim in rec.score.dimensionen:
            allowed.update({round(dim.rohwert, 2), round(dim.gewicht, 4), round(dim.beitrag, 4)})
            allowed.update(round(k.wert, 2) for k in dim.komponenten)
        if rec.vergleich:
            v = rec.vergleich
            allowed.update(
                abs(float(x))
                for x in (
                    v.punkte_vorsprung, v.preis_differenz_eur, v.km_differenz,
                    v.kosten_differenz_eur,
                )
                if x is not None
            )
    return allowed


def score_faithfulness(
    antwort: str,
    ranking,
    state: Optional[InterviewState] = None,
    toleranz: float = 0.02,
) -> FaithfulnessScore:
    """Every figure in the reply has to trace back to one the agent was given.

    A small relative tolerance absorbs honest rounding in narration, "about 25,000"
    against 25,490. It does not absorb an invented figure, which is the thing being
    looked for.
    """
    allowed = erlaubte_zahlen(ranking, state)
    found = numbers_in(antwort)

    belegt, erfunden = 0, []
    for raw, value in found:
        if abs(value) < KLEINZAHL_GRENZE:
            belegt += 1  # ordinals and counts, not claims about the data
            continue
        if any(
            abs(value - a) <= max(toleranz * max(abs(a), 1.0), 0.5) for a in allowed
        ):
            belegt += 1
        else:
            erfunden.append(raw)

    return FaithfulnessScore(
        zahlen_im_text=len(found),
        zahlen_belegt=belegt,
        erfundene_zahlen=erfunden[:8],
    )
