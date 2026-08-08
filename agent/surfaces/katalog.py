"""A2UI surface for the ranked catalogue. Mandatory requirement M-4.

The surface is built from the ranking engine's output and nothing else. No scoring,
no filtering and no cost arithmetic happens here or anywhere in the interface layer:
this module translates a `RankingResult` into A2UI messages and stops.

Wire format is A2UI v0.9, read from the core's own message processor tests rather
than from prose. An earlier version of this module emitted v0.8 (`beginRendering` and
`surfaceUpdate`, with values wrapped as `{"literal": ...}`); the renderer is v0.9 and
silently rendered nothing, which is how the mistake was found.

    {"version": "v0.9", "createSurface":    {"surfaceId": ..., "catalogId": ...}}
    {"version": "v0.9", "updateComponents": {"surfaceId": ..., "components": [...]}}
    {"version": "v0.9", "updateDataModel":  {"surfaceId": ..., "path": ..., "contents": ...}}

Components are flat: `{"id": ..., "component": "Name", ...props}`. The renderer always
mounts the component whose id is `root`.

Weight changes go out as `updateComponents` for the affected cards alone, so the
surface updates in place instead of being torn down and rebuilt. That incremental
path is the requirement, not an optimisation.
"""

from __future__ import annotations

from typing import Any

from agent import i18n
from agent.i18n import DEFAULT_LANG, Lang
from agent.tools.ranking import RankingResult, constraint_label

SURFACE_ID = "fahrbereit-katalog"
CATALOG_ID = "fahrbereit/v1"


def _component(component_id: str, name: str, props: dict[str, Any]) -> dict[str, Any]:
    """A v0.9 component node: id, component name, then props flat on the same object."""
    return {"id": component_id, "component": name, **props}


def _msg(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"version": "v0.9", kind: payload}


def _eckdaten(listing, lang: Lang = DEFAULT_LANG) -> str:
    """The headline specification line, in the order a German listing quotes it."""
    teile = [
        f"EZ {listing.erstzulassung}" if lang == "de" else f"reg. {listing.erstzulassung}",
        f"{i18n.fmt_int(listing.kilometerstand, lang)} km",
        f"{listing.leistung_kw} kW ({listing.leistung_ps} PS)",
        i18n.getriebe(listing.getriebe, lang),
        i18n.kraftstoff(listing.kraftstoff, lang),
    ]
    return " · ".join(teile)


def _preis(listing, lang: Lang = DEFAULT_LANG) -> str:
    betrag = i18n.fmt_int(listing.preis_referenz(), lang)
    if listing.listing_type == "kauf":
        return f"{betrag} EUR"
    return f"{betrag} EUR/Tag" if lang == "de" else f"{betrag} EUR/day"


def build_messages(
    result: RankingResult,
    ueberschrift: str | None = None,
    lang: Lang = DEFAULT_LANG,
) -> list[dict]:
    """Translate a ranking result into an ordered list of A2UI messages."""
    ueberschrift = ueberschrift or i18n.t("empfehlungen", lang)
    components: list[dict[str, Any]] = []
    kinder: list[str] = []

    components.append(
        _component(
            "kopf",
            "Kopfzeile",
            {
                "titel": ueberschrift,
                "untertitel": result.report.erklaerung(lang),
            },
        )
    )
    kinder.append("kopf")

    ausgeschlossen = [
        {"grund": constraint_label(key, lang), "anzahl": count}
        for key, count in result.report.ausgeschlossen.items()
    ]
    components.append(
        _component(
            "filter",
            "FilterBericht",
            {
                "gesamt": result.report.gesamt,
                "uebrig": result.report.uebrig,
                "ausgeschlossen": ausgeschlossen,
            },
        )
    )
    kinder.append("filter")

    components.append(
        _component(
            "gewichte",
            "GewichtungsPanel",
            {
                "gewichte": [
                    {"name": i18n.t(f"dim.{name}", lang), "anteil": round(anteil, 4)}
                    for name, anteil in sorted(result.gewichte.items(), key=lambda kv: -kv[1])
                ],
                "hinweis": (
                    "Die Voreinstellung ist ein Startpunkt, kein Urteil. "
                    "Jede Dimension ist einstellbar."
                    if lang == "de"
                    else "The default is a starting position, not a verdict. "
                         "Every dimension is adjustable."
                ),
            },
        )
    )
    kinder.append("gewichte")

    for rec in result.empfehlungen:
        listing = rec.listing
        karte_id = f"karte-{listing.id}"
        dimensionen = [
            {
                "label": dim.label,
                "wert": dim.rohwert,
                "gewicht": dim.gewicht,
                "beitrag": dim.beitrag,
                "begruendung": dim.begruendung,
                "begrenztDurch": dim.begrenzt_durch or "",
                "komponenten": [
                    {"name": c.name, "wert": c.wert, "detail": c.detail}
                    for c in dim.komponenten
                ],
            }
            for dim in rec.score.dimensionen
        ]

        vergleich = ""
        if rec.vergleich:
            v = rec.vergleich
            preis_delta = ("+" if v.preis_differenz_eur >= 0 else "-") + i18n.fmt_int(
                abs(v.preis_differenz_eur), lang
            )
            km_delta = ("+" if v.km_differenz >= 0 else "-") + i18n.fmt_int(
                abs(v.km_differenz), lang
            )
            if lang == "de":
                vergleich = (
                    f"{v.punkte_vorsprung:+.1f} Punkte gegenüber {v.gegen_bezeichnung}, "
                    f"{preis_delta} EUR Preis, {km_delta} km Laufleistung"
                )
            else:
                vergleich = (
                    f"{v.punkte_vorsprung:+.1f} points ahead of {v.gegen_bezeichnung}, "
                    f"{preis_delta} EUR price, {km_delta} km mileage"
                )

        components.append(
            _component(
                karte_id,
                "FahrzeugKarte",
                {
                    "listingId": listing.id,
                    "rang": rec.rang,
                    "bezeichnung": listing.bezeichnung,
                    "kategorie": i18n.kategorie(listing.category, lang),
                    "eckdaten": _eckdaten(listing, lang),
                    "preis": _preis(listing, lang),
                    "haendler": f"{listing.haendler}, {listing.standort_plz} {listing.standort_ort}",
                    "punkte": rec.score.total,
                    "basisAnzahl": rec.score.basis_anzahl,
                    "relativHinweis": rec.score.relativ_hinweis_lang(lang),
                    "dimensionen": dimensionen,
                    "topFaktoren": rec.score.top_faktoren(lang=lang),
                    "schwachstellen": rec.score.schwachstellen(lang=lang),
                    "vergleich": vergleich,
                    "tcoGesamt": rec.tco_gesamt_eur or 0,
                    "istMiete": listing.listing_type == "miete",
                },
            )
        )
        kinder.append(karte_id)

    components.append(_component("root", "Spalte", {"kinder": kinder}))

    return [
        _msg("createSurface", {"surfaceId": SURFACE_ID, "catalogId": CATALOG_ID}),
        _msg("updateComponents", {"surfaceId": SURFACE_ID, "components": components}),
    ]


def build_weight_update(
    result: RankingResult, lang: Lang = DEFAULT_LANG
) -> list[dict]:
    """Weights only, as a data model update.

    Sent on its own when the user moves a weight, so the surface updates in place
    rather than being torn down and rebuilt. FR-034.
    """
    return [
        _msg(
            "updateComponents",
            {
                "surfaceId": SURFACE_ID,
                "components": [
                    _component(
                        "gewichte",
                        "GewichtungsPanel",
                        {
                            "gewichte": [
                                {
                                    "name": i18n.t(f"dim.{name}", lang),
                                    "anteil": round(anteil, 4),
                                }
                                for name, anteil in sorted(
                                    result.gewichte.items(), key=lambda kv: -kv[1]
                                )
                            ],
                            "hinweis": (
                                "Die Voreinstellung ist ein Startpunkt, kein Urteil. "
                                "Jede Dimension ist einstellbar."
                                if lang == "de"
                                else "The default is a starting position, not a verdict. "
                                     "Every dimension is adjustable."
                            ),
                        },
                    )
                ],
            },
        )
    ]
