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
from mcpapps.shared.style import CSS

RESOURCE_URI = "ui://kasse/checkout.html"

BANNER = (
    '<div class="sim-banner">'
    f"<strong>{SIMULATION_TOKEN}</strong> &nbsp; Dies ist eine Vorführung. "
    "Es wird kein Geld bewegt, keine Bank kontaktiert und kein Vertrag geschlossen."
    "</div>"
)


def euro(cent: int) -> str:
    return f"{cent / 100:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")


def _render(order: dict[str, Any]) -> str:
    positionen = order["positionen"]
    rows = "".join(
        f"<tr><td>{p['bezeichnung']}</td>"
        f'<td class="num dim">{p["menge"]}</td>'
        f'<td class="num">{euro(p["einzelpreis_cent"])}</td></tr>'
        for p in positionen
    )
    vertragsart = "Kaufvertrag" if order["intent"] == "kauf" else "Mietvertrag"

    miet_block = ""
    if order["intent"] == "miete":
        miet_block = f"""
      <hr>
      <div class="eyebrow">Abholung</div>
      <table>
        <tr><td>Station</td><td class="num">{order.get('abholort', '-')}</td></tr>
        <tr><td>Zeitraum</td><td class="num">{order.get('zeitraum', '-')}</td></tr>
        <tr><td>Kaution, erstattbar</td>
            <td class="num">{euro(order.get('kaution_cent', 0))} EUR</td></tr>
      </table>"""

    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kasse</title>
<style>{CSS}</style>
</head>
<body>
  {BANNER}

  <div class="eyebrow">fahrbereit &middot; Kasse</div>
  <h1>{order['fahrzeug']}</h1>
  <div class="dim" style="font-size:12px;margin-top:4px">Angebot {order['listing_id']}</div>

  <hr>
  <div class="eyebrow">Rechnungsposten</div>
  <table>
    <tr><th>Position</th><th class="num">Menge</th><th class="num">EUR</th></tr>
    {rows}
  </table>

  <hr>
  <table>
    <tr><td class="dim">Nettobetrag</td>
        <td class="num">{euro(order['netto_cent'])}</td></tr>
    <tr><td class="dim">zzgl. 19 % MwSt.</td>
        <td class="num">{euro(order['mwst_cent'])}</td></tr>
    <tr class="total"><td>Gesamtbetrag</td>
        <td class="num">{euro(order['brutto_cent'])}</td></tr>
  </table>
  {miet_block}

  <hr>
  <div class="eyebrow">Zahlung per SEPA-Überweisung, simuliert</div>
  <table>
    <tr><td class="dim">Empfänger</td><td class="num">fahrbereit Demo GmbH</td></tr>
    <tr><td class="dim">IBAN</td><td class="num ref">{SIMULATION_IBAN}</td></tr>
    <tr><td class="dim">BIC</td><td class="num ref">{SIMULATION_BIC}</td></tr>
  </table>
  <div class="footnote">
    Die IBAN ist absichtlich ungültig. Die Prüfziffer 00 kann in keiner echten IBAN
    vorkommen. Es existiert in dieser Anwendung kein Feld für Kartendaten.
  </div>

  <div style="margin-top:20px">
    <button id="pay">{vertragsart} simulieren</button>
  </div>
  <div class="status" id="status"></div>

  <div id="beleg" style="display:none">
    <hr>
    <div class="watermark" style="border:1px solid var(--rule);padding:18px">
      <div class="eyebrow">{vertragsart}, simuliert</div>
      <h2 id="beleg-titel">Bestätigung</h2>
      <table>
        <tr><td class="dim">Vertragsreferenz</td>
            <td class="num ref" id="vertrag-ref">-</td></tr>
        <tr><td class="dim">Zahlungsreferenz</td>
            <td class="num ref" id="zahl-ref">-</td></tr>
        <tr><td class="dim">Status</td><td class="num" id="beleg-status">-</td></tr>
        <tr class="total"><td>Gesamtbetrag</td>
            <td class="num">{euro(order['brutto_cent'])}</td></tr>
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
    statusEl.textContent = 'Simulierte Zahlung wird verarbeitet...';
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
        ? 'Simulation abgeschlossen. Es wurde kein Geld bewegt.'
        : 'Simulierte Zahlung fehlgeschlagen.';
      if (!payload.erfolgreich) payBtn.disabled = false;
    }} catch (err) {{
      statusEl.className = 'status err';
      statusEl.textContent = 'Fehler: ' + err;
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
) -> dict[str, Any]:
    netto, mwst = split_mwst(brutto_cent)
    bezeichnung = "Fahrzeugkaufpreis" if intent == "kauf" else "Mietbetrag"
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
        f"Gesamt {euro(order['brutto_cent'])} EUR. Es wird kein Geld bewegt."
    )


apps.add_html_resource(
    RESOURCE_URI,
    _render(build_order("FB-00000", "Fahrzeug", "kauf", 0)),
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


def render_for(order: dict[str, Any]) -> str:
    """Exposed for tests and for the React host."""
    return _render(order)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(mcp.streamable_http_app(), host="0.0.0.0", port=3002, log_level="warning")
