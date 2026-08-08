"""kasse: the simulated checkout, as an MCP App. Mandatory requirements M-3 and M-5.

There is no card form in this file. Not a disabled one, not a placeholder one. The
component set does not contain the concept, which makes the violation impossible
rather than merely avoided.

Three independent simulation signals, because one can be scrolled past: a persistent
banner at the top, a watermark across the confirmation document, and the literal token
SIMULATION inside every generated reference. There is no scroll position of this
surface at which a reasonable person could believe money moved.
"""

from __future__ import annotations

import json
from typing import Any

from mcp.server import MCPServer
from mcp.server.apps import Apps
from mcp.server.mcpserver.context import Context

from agent.payment import (
    SIMULATION_BIC,
    SIMULATION_IBAN,
    SIMULATION_TOKEN,
    LineItem,
    get_payment_provider,
    split_mwst,
)
from agent import i18n
from agent.i18n import DEFAULT_LANG, Lang
from mcpapps.shared.style import CSS

RESOURCE_URI = "ui://kasse/checkout.html"

def banner(lang: Lang = DEFAULT_LANG) -> str:
    """The token itself never translates. It must read identically everywhere."""
    return (
        '<div class="sim-banner">'
        f"<strong>{SIMULATION_TOKEN}</strong> &nbsp; {i18n.t('kasse.banner', lang)}"
        "</div>"
    )


def euro(cent: int, lang: Lang = DEFAULT_LANG) -> str:
    """Two decimals, with separators following the language."""
    return i18n.fmt_dec(cent / 100, lang, places=2)


def _render(order: dict[str, Any], lang: Lang = DEFAULT_LANG) -> str:
    positionen = order["positionen"]
    rows = "".join(
        f"<tr><td>{p['bezeichnung']}</td>"
        f'<td class="num dim">{p["menge"]}</td>'
        f'<td class="num">{euro(p['einzelpreis_cent'], lang)}</td></tr>'
        for p in positionen
    )
    ist_kauf = order["intent"] == "kauf"
    vertragsart = i18n.t("kasse.kaufvertrag" if ist_kauf else "kasse.mietvertrag", lang)
    btn_label = i18n.t("kasse.btn_kauf" if ist_kauf else "kasse.btn_miete", lang)

    miet_block = ""
    if order["intent"] == "miete":
        miet_block = f"""
      <hr>
      <div class="eyebrow">{i18n.t("kasse.abholung", lang)}</div>
      <table>
        <tr><td>{i18n.t("kasse.station", lang)}</td><td class="num">{order.get('abholort', '-')}</td></tr>
        <tr><td>{i18n.t("kasse.zeitraum", lang)}</td><td class="num">{order.get('zeitraum', '-')}</td></tr>
        <tr><td>{i18n.t("kasse.kaution", lang)}</td>
            <td class="num">{euro(order.get('kaution_cent', 0), lang)} EUR</td></tr>
      </table>"""

    return f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{i18n.t("kasse", lang)}</title>
<style>{CSS}</style>
</head>
<body>
  {banner(lang)}

  <div class="eyebrow">fahrbereit &middot; {i18n.t("kasse", lang)}</div>
  <h1>{order['fahrzeug']}</h1>
  <div class="dim" style="font-size:12px;margin-top:4px">{i18n.t("form.angebot", lang)} {order['listing_id']}</div>

  <hr>
  <div class="eyebrow">{i18n.t("kasse.rechnungsposten", lang)}</div>
  <table>
    <tr><th>{i18n.t("kasse.position", lang)}</th><th class="num">{i18n.t("kasse.menge", lang)}</th><th class="num">EUR</th></tr>
    {rows}
  </table>

  <hr>
  <table>
    <tr><td class="dim">{i18n.t("kasse.netto", lang)}</td>
        <td class="num">{euro(order['netto_cent'], lang)}</td></tr>
    <tr><td class="dim">{i18n.t("kasse.mwst", lang)}</td>
        <td class="num">{euro(order['mwst_cent'], lang)}</td></tr>
    <tr class="total"><td>{i18n.t("kasse.brutto", lang)}</td>
        <td class="num">{euro(order['brutto_cent'], lang)}</td></tr>
  </table>
  {miet_block}

  <hr>
  <div class="eyebrow">{i18n.t("kasse.zahlung", lang)}</div>
  <table>
    <tr><td class="dim">{i18n.t("kasse.empfaenger", lang)}</td><td class="num">fahrbereit Demo GmbH</td></tr>
    <tr><td class="dim">IBAN</td><td class="num ref">{SIMULATION_IBAN}</td></tr>
    <tr><td class="dim">BIC</td><td class="num ref">{SIMULATION_BIC}</td></tr>
  </table>
  <div class="footnote">{i18n.t("kasse.iban_hinweis", lang)}</div>

  <div style="margin-top:20px">
    <button id="pay">{btn_label}</button>
  </div>
  <div class="status" id="status"></div>

  <div id="beleg" style="display:none">
    <hr>
    <div class="watermark" style="border:1px solid var(--rule);padding:18px">
      <div class="eyebrow">{vertragsart}, {i18n.t("kasse.simuliert_suffix", lang)}</div>
      <h2 id="beleg-titel">{i18n.t("kasse.bestaetigung", lang)}</h2>
      <table>
        <tr><td class="dim">{i18n.t("kasse.vertrag_ref", lang)}</td>
            <td class="num ref" id="vertrag-ref">-</td></tr>
        <tr><td class="dim">{i18n.t("kasse.zahl_ref", lang)}</td>
            <td class="num ref" id="zahl-ref">-</td></tr>
        <tr><td class="dim">{i18n.t("kasse.status", lang)}</td><td class="num" id="beleg-status">-</td></tr>
        <tr class="total"><td>{i18n.t("kasse.brutto", lang)}</td>
            <td class="num">{euro(order['brutto_cent'], lang)}</td></tr>
      </table>
      <div class="footnote" id="beleg-hinweis"></div>
    </div>
  </div>

<script>
  const LISTING = {json.dumps(order['listing_id'])};
  const INTENT = {json.dumps(order['intent'])};
  const statusEl = document.getElementById('status');
  const payBtn = document.getElementById('pay');

  payBtn.addEventListener('click', async () => {{
    payBtn.disabled = true;
    statusEl.className = 'status';
    statusEl.textContent = {json.dumps(i18n.t("kasse.verarbeitet", lang))};
    try {{
      const raw = await window.mcp.callTool('kasse_bestaetigen', {{
        listing_id: LISTING, intent: INTENT,
      }});
      const text = typeof raw === 'string' ? raw : JSON.stringify(raw);
      const payload = JSON.parse(
        (text.match(/\\{{[\\s\\S]*\\}}/) || [text])[0]
      );
      document.getElementById('vertrag-ref').textContent = payload.vertrag_referenz;
      document.getElementById('zahl-ref').textContent = payload.zahlung_referenz;
      document.getElementById('beleg-status').textContent = payload.status;
      document.getElementById('beleg-hinweis').textContent = payload.meldung;
      document.getElementById('beleg').style.display = 'block';
      statusEl.className = payload.erfolgreich ? 'status ok' : 'status err';
      statusEl.textContent = payload.erfolgreich
        ? {json.dumps(i18n.t("kasse.fertig", lang))}
        : {json.dumps(i18n.t("kasse.fehlgeschlagen", lang))};
      if (!payload.erfolgreich) payBtn.disabled = false;
    }} catch (err) {{
      statusEl.className = 'status err';
      statusEl.textContent = {json.dumps(i18n.t("fehler", lang))} + ': ' + err;
      payBtn.disabled = false;
    }}
  }});
</script>
</body></html>
"""


def build_order(
    listing_id: str,
    fahrzeug: str,
    intent: str,
    brutto_cent: int,
    kaution_cent: int = 0,
    abholort: str = "",
    zeitraum: str = "",
    lang: Lang = DEFAULT_LANG,
) -> dict[str, Any]:
    netto, mwst = split_mwst(brutto_cent)
    bezeichnung = (
        ("Fahrzeugkaufpreis" if intent == "kauf" else "Mietbetrag")
        if lang == "de"
        else ("Vehicle purchase price" if intent == "kauf" else "Rental amount")
    )
    return {
        "listing_id": listing_id,
        "fahrzeug": fahrzeug,
        "intent": intent,
        "positionen": [
            {"bezeichnung": bezeichnung, "menge": 1, "einzelpreis_cent": brutto_cent}
        ],
        "netto_cent": netto,
        "mwst_cent": mwst,
        "brutto_cent": brutto_cent,
        "kaution_cent": kaution_cent,
        "abholort": abholort,
        "zeitraum": zeitraum,
    }


apps = Apps()

OFFENE_BESTELLUNGEN: dict[str, dict[str, Any]] = {}


@apps.tool(
    resource_uri=RESOURCE_URI,
    description=(
        "Öffnet die simulierte Kasse in der Unterhaltung. Zeigt Rechnungsposten, "
        "19 Prozent MwSt. getrennt ausgewiesen, und schließt mit einem simulierten "
        "Vertrag ab. Es wird kein Geld bewegt."
    ),
)
def kasse_oeffnen(
    ctx: Context,
    listing_id: str,
    fahrzeug: str = "",
    intent: str = "kauf",
    betrag_eur: int = 0,
) -> str:
    order = build_order(listing_id, fahrzeug or listing_id, intent, betrag_eur * 100)
    OFFENE_BESTELLUNGEN[listing_id] = order
    netto, mwst = order["netto_cent"], order["mwst_cent"]
    return (
        f"SIMULATION. Kasse für {fahrzeug or listing_id} geöffnet. "
        f"Netto {euro(netto)} EUR, MwSt. {euro(mwst)} EUR, "
        f"Gesamt {euro(order['brutto_cent'], lang)} EUR. Es wird kein Geld bewegt."
    )


apps.add_html_resource(
    RESOURCE_URI,
    _render(build_order("FB-00000", "Fahrzeug", "kauf", 0), DEFAULT_LANG),
    title="Kasse, simuliert",
    description="Simulierter Checkout. Kein echter Zahlungsverkehr.",
)

mcp = MCPServer("fahrbereit-kasse", extensions=[apps])


@mcp.tool(description="Schließt die simulierte Zahlung ab und erzeugt den Vertrag.")
def kasse_bestaetigen(listing_id: str, intent: str = "kauf") -> str:
    """Confirms through the payment seam. No vendor is named here."""
    order = OFFENE_BESTELLUNGEN.get(listing_id)
    if order is None:
        order = build_order(listing_id, listing_id, intent, 0)

    provider = get_payment_provider()
    positionen = [LineItem(**p) for p in order["positionen"]]
    intent_obj = provider.create_intent(positionen, referenz_praefix="FB-ZAHL")
    result = provider.confirm(intent_obj)

    vertrag_praefix = "KV" if intent == "kauf" else "MV"
    vertrag_referenz = intent_obj.referenz.replace("FB-ZAHL", f"FB-{vertrag_praefix}")

    return json.dumps(
        {
            "erfolgreich": result.erfolgreich,
            "status": result.status.value,
            "vertrag_referenz": vertrag_referenz,
            "zahlung_referenz": result.referenz,
            "meldung": result.meldung,
            "iban": result.iban,
            "simuliert": True,
        },
        ensure_ascii=False,
    )


@mcp.tool(
    description=(
        "Liefert die gerenderte Kasse für einen konkreten Fall. Der ui://-Eintrag "
        "bleibt die Kennung der App; dieser Aufruf liefert die Variante für Betrag, "
        "Flow und Sprache. Alles daran ist simuliert."
    )
)
def kasse_render(
    listing_id: str,
    fahrzeug: str = "",
    intent: str = "kauf",
    betrag_eur: int = 0,
    kaution_eur: int = 0,
    abholort: str = "",
    zeitraum: str = "",
    lang: str = "de",
) -> str:
    norm = i18n.normalise(lang)
    order = build_order(
        listing_id,
        fahrzeug or listing_id,
        intent,
        betrag_eur * 100,
        kaution_cent=kaution_eur * 100,
        abholort=abholort,
        zeitraum=zeitraum,
        lang=norm,
    )
    OFFENE_BESTELLUNGEN[listing_id] = order
    return _render(order, norm)


def render_for(order: dict[str, Any], lang: str = DEFAULT_LANG) -> str:
    """Exposed for tests and for the React host."""
    return _render(order, i18n.normalise(lang))


def _serve(mcp_server, default_port: int) -> None:
    """Run this MCP server over streamable HTTP.

    DNS rebinding protection is on by default and rejects any Host header it does not
    recognise, which under compose means the service name: the server answered every
    request with 421 Misdirected Request and "Invalid Host header: formular:3001".
    The allowed hosts therefore have to include the service name the backend dials.
    """
    import os

    import uvicorn
    from mcp.server.transport_security import TransportSecuritySettings

    port = int(os.environ.get("PORT", default_port))
    service = os.environ.get("MCP_SERVICE_NAME", "")
    allowed = [f"127.0.0.1:{port}", f"localhost:{port}", f"0.0.0.0:{port}"]
    if service:
        allowed += [f"{service}:{port}", service]

    app = mcp_server.streamable_http_app(
        transport_security=TransportSecuritySettings(
            allowed_hosts=allowed,
            allowed_origins=["*"],
        )
    )
    uvicorn.run(app, host=os.environ.get("HOST", "0.0.0.0"), port=port, log_level="warning")


if __name__ == "__main__":
    _serve(mcp, 3002)
