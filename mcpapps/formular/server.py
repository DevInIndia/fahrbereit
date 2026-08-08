"""formular: the in-chat intake form, as an MCP App. Mandatory requirement M-2.

The tool carries `_meta.ui.resourceUri`; the surface behind that URI is a single
self-contained HTML document served as a `ui://` resource with the MCP App mime type.
The host renders it in a sandboxed iframe and the surface talks back over the bridge.

The point of doing it this way rather than as a link is that the user never leaves the
conversation. Milestone 1 keeps this to three fields per flow.
"""

from __future__ import annotations

import json
from typing import Any

from mcp.server import MCPServer
from mcp.server.apps import Apps
from mcp.server.mcpserver.context import Context

from mcpapps.shared.style import CSS

RESOURCE_URI = "ui://formular/intake.html"

# Milestone 1 scope: three fields per flow, no validation beyond required. The full
# field set from data-model.md arrives in Milestone 2.
FELDER: dict[str, list[dict[str, Any]]] = {
    "kauf": [
        {"name": "name", "label": "Name", "type": "text", "placeholder": "Vor- und Nachname"},
        {"name": "email", "label": "E-Mail", "type": "email", "placeholder": "name@beispiel.de"},
        {
            "name": "zahlungsart",
            "label": "Zahlungsart",
            "type": "select",
            "options": ["Barzahlung", "Finanzierung"],
        },
    ],
    "miete": [
        {"name": "name", "label": "Name", "type": "text", "placeholder": "Vor- und Nachname"},
        {
            "name": "fuehrerschein_seit",
            "label": "Führerschein seit",
            "type": "number",
            "placeholder": "2015",
        },
        {
            "name": "versicherung",
            "label": "Versicherungsschutz",
            "type": "select",
            "options": ["Basis", "Komfort", "Premium"],
        },
    ],
}


def _render(intent: str, fahrzeug: str, listing_id: str) -> str:
    felder = FELDER.get(intent, FELDER["kauf"])
    titel = "Kaufanfrage" if intent == "kauf" else "Mietanfrage"

    rows = []
    for feld in felder:
        if feld["type"] == "select":
            options = "".join(f'<option value="{o}">{o}</option>' for o in feld["options"])
            control = f'<select id="{feld["name"]}" name="{feld["name"]}">{options}</select>'
        else:
            control = (
                f'<input id="{feld["name"]}" name="{feld["name"]}" '
                f'type="{feld["type"]}" placeholder="{feld.get("placeholder", "")}">'
            )
        rows.append(
            f'<div class="col-6">'
            f'<label for="{feld["name"]}">{feld["label"]}</label>'
            f"{control}"
            f'<div class="error" id="err-{feld["name"]}"></div>'
            f"</div>"
        )

    feld_namen = json.dumps([f["name"] for f in felder])

    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titel}</title>
<style>{CSS}</style>
</head>
<body>
  <div class="eyebrow">fahrbereit &middot; {titel}</div>
  <h1>{fahrzeug}</h1>
  <div class="dim" style="font-size:12px;margin-top:4px">Angebot {listing_id}</div>
  <hr>

  <form id="f" novalidate>
    <div class="grid">
      {"".join(rows)}
    </div>
    <div style="margin-top:18px">
      <button type="submit" id="submit">Weiter zur Kasse</button>
    </div>
  </form>

  <div class="status" id="status"></div>
  <div class="footnote">
    Ihre Angaben bleiben in dieser Unterhaltung. Es findet keine Weitergabe statt,
    und es wird keine echte Buchung ausgelöst.
  </div>

<script>
  const FELDER = {feld_namen};
  const INTENT = {json.dumps(intent)};
  const LISTING = {json.dumps(listing_id)};
  const statusEl = document.getElementById('status');

  function validate(data) {{
    const errors = {{}};
    for (const name of FELDER) {{
      if (!String(data[name] ?? '').trim()) errors[name] = 'Pflichtfeld';
    }}
    if (data.email && !/^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$/.test(data.email)) {{
      errors.email = 'Bitte eine gültige E-Mail-Adresse angeben';
    }}
    if (data.fuehrerschein_seit) {{
      const jahr = Number(data.fuehrerschein_seit);
      const jetzt = new Date().getFullYear();
      if (!Number.isInteger(jahr) || jahr < 1950 || jahr > jetzt) {{
        errors.fuehrerschein_seit = 'Jahr zwischen 1950 und ' + jetzt;
      }}
    }}
    return errors;
  }}

  function showErrors(errors) {{
    for (const name of FELDER) {{
      const box = document.getElementById('err-' + name);
      const field = document.getElementById(name);
      const message = errors[name] || '';
      if (box) box.textContent = message;
      if (field) field.setAttribute('aria-invalid', message ? 'true' : 'false');
    }}
  }}

  document.getElementById('f').addEventListener('submit', async (event) => {{
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.target).entries());
    const errors = validate(data);
    showErrors(errors);
    if (Object.keys(errors).length) {{
      statusEl.className = 'status err';
      statusEl.textContent = 'Bitte die markierten Felder prüfen.';
      return;
    }}

    statusEl.className = 'status';
    statusEl.textContent = 'Wird übernommen...';
    document.getElementById('submit').disabled = true;
    try {{
      const result = await window.mcp.callTool('formular_absenden', {{
        listing_id: LISTING, intent: INTENT, daten: JSON.stringify(data),
      }});
      statusEl.className = 'status ok';
      statusEl.textContent = 'Übernommen. Die Unterhaltung geht weiter.';
    }} catch (err) {{
      statusEl.className = 'status err';
      statusEl.textContent = 'Fehler: ' + err;
      document.getElementById('submit').disabled = false;
    }}
  }});
</script>
</body></html>
"""


apps = Apps()

# Milestone 1 keeps submitted data in process. Milestone 2 writes it into the
# persisted session store, which is where it belongs.
EINGEREICHT: dict[str, dict[str, Any]] = {}


@apps.tool(
    resource_uri=RESOURCE_URI,
    description=(
        "Öffnet das Formular für Käufer- oder Mieterdaten direkt in der Unterhaltung. "
        "Aufrufen, sobald der Nutzer ein Fahrzeug ausgewählt hat."
    ),
)
def formular_oeffnen(
    ctx: Context, listing_id: str, intent: str = "kauf", fahrzeug: str = ""
) -> str:
    """Opens the intake form. Returns text too, so clients without Apps get something."""
    art = "Kaufanfrage" if intent == "kauf" else "Mietanfrage"
    return (
        f"{art} für {fahrzeug or listing_id} geöffnet. "
        f"Bitte Name, Kontakt und die dritte Angabe im Formular ausfüllen."
    )


apps.add_html_resource(
    RESOURCE_URI,
    _render("kauf", "Fahrzeug", "FB-00000"),
    title="Anfrageformular",
    description="Käufer- und Mieterdaten, direkt in der Unterhaltung.",
)

mcp = MCPServer("fahrbereit-formular", extensions=[apps])


@mcp.tool(description="Nimmt die im Formular eingegebenen Daten entgegen.")
def formular_absenden(listing_id: str, intent: str, daten: str) -> str:
    """Called from inside the surface over the app bridge."""
    try:
        werte = json.loads(daten)
    except json.JSONDecodeError:
        return "Formulardaten konnten nicht gelesen werden."
    EINGEREICHT[listing_id] = {"intent": intent, **werte}
    felder = ", ".join(f"{k}={v}" for k, v in werte.items())
    return f"Formular für {listing_id} übernommen: {felder}"


@mcp.tool(description="Liest die zuletzt eingereichten Formulardaten zu einem Angebot.")
def formular_daten(listing_id: str) -> str:
    werte = EINGEREICHT.get(listing_id)
    if not werte:
        return f"Für {listing_id} liegen keine Formulardaten vor."
    return json.dumps(werte, ensure_ascii=False)


def render_for(intent: str, fahrzeug: str, listing_id: str) -> str:
    """Exposed for tests and for the React host, which renders the flow specific variant."""
    return _render(intent, fahrzeug, listing_id)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(mcp.streamable_http_app(), host="0.0.0.0", port=3001, log_level="warning")
