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

from agent import i18n
from agent.i18n import DEFAULT_LANG, Lang
from mcpapps.shared.style import CSS

RESOURCE_URI = "ui://formular/intake.html"

# Milestone 1 scope: three fields per flow, no validation beyond required. The full
# field set from data-model.md arrives in Milestone 2.
def felder(intent: str, lang: Lang = DEFAULT_LANG) -> list[dict[str, Any]]:
    """Three fields per flow, labelled in the requested language."""
    if intent == "miete":
        return [
            {"name": "name", "label": i18n.t("form.name", lang), "type": "text",
             "placeholder": i18n.t("form.name_ph", lang)},
            {"name": "fuehrerschein_seit", "label": i18n.t("form.fs_seit", lang),
             "type": "number", "placeholder": "2015"},
            {"name": "versicherung", "label": i18n.t("form.versicherung", lang),
             "type": "select",
             "options": [i18n.t("form.basis", lang), i18n.t("form.komfort", lang),
                         i18n.t("form.premium", lang)]},
        ]
    return [
        {"name": "name", "label": i18n.t("form.name", lang), "type": "text",
         "placeholder": i18n.t("form.name_ph", lang)},
        {"name": "email", "label": i18n.t("form.email", lang), "type": "email",
         "placeholder": "name@beispiel.de"},
        {"name": "zahlungsart", "label": i18n.t("form.zahlungsart", lang), "type": "select",
         "options": [i18n.t("form.barzahlung", lang), i18n.t("form.finanzierung", lang)]},
    ]


def _render(
    intent: str, fahrzeug: str, listing_id: str, lang: Lang = DEFAULT_LANG
) -> str:
    feld_liste = felder(intent, lang)
    titel = i18n.t("form.kaufanfrage" if intent == "kauf" else "form.mietanfrage", lang)

    rows = []
    for feld in feld_liste:
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

    feld_namen = json.dumps([f["name"] for f in feld_liste])

    return f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titel}</title>
<style>{CSS}</style>
</head>
<body>
  <div class="eyebrow">fahrbereit &middot; {titel}</div>
  <h1>{fahrzeug}</h1>
  <div class="dim" style="font-size:12px;margin-top:4px">{i18n.t("form.angebot", lang)} {listing_id}</div>
  <hr>

  <form id="f" novalidate>
    <div class="grid">
      {"".join(rows)}
    </div>
    <div style="margin-top:18px">
      <button type="submit" id="submit">{i18n.t("form.weiter", lang)}</button>
    </div>
  </form>

  <div class="status" id="status"></div>
  <div class="footnote">{i18n.t("form.fussnote", lang)}</div>

<script>
  const FELDER = {feld_namen};
  const INTENT = {json.dumps(intent)};
  const LISTING = {json.dumps(listing_id)};
  const statusEl = document.getElementById('status');

  function validate(data) {{
    const errors = {{}};
    for (const name of FELDER) {{
      if (!String(data[name] ?? '').trim()) errors[name] = {json.dumps(i18n.t("form.pflichtfeld", lang))};
    }}
    if (data.email && !/^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$/.test(data.email)) {{
      errors.email = {json.dumps(i18n.t("form.email_ungueltig", lang))};
    }}
    if (data.fuehrerschein_seit) {{
      const jahr = Number(data.fuehrerschein_seit);
      const jetzt = new Date().getFullYear();
      if (!Number.isInteger(jahr) || jahr < 1950 || jahr > jetzt) {{
        errors.fuehrerschein_seit = {json.dumps(i18n.t("form.jahr_zwischen", lang))} + ' ' + jetzt;
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
      statusEl.textContent = {json.dumps(i18n.t("form.pruefen", lang))};
      return;
    }}

    statusEl.className = 'status';
    statusEl.textContent = {json.dumps(i18n.t("form.wird_uebernommen", lang))};
    document.getElementById('submit').disabled = true;
    try {{
      const result = await window.mcp.callTool('formular_absenden', {{
        listing_id: LISTING, intent: INTENT, daten: JSON.stringify(data),
      }});
      statusEl.className = 'status ok';
      statusEl.textContent = {json.dumps(i18n.t("form.uebernommen", lang))};
    }} catch (err) {{
      statusEl.className = 'status err';
      statusEl.textContent = {json.dumps(i18n.t("fehler", lang))} + ': ' + err;
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
    _render("kauf", "Fahrzeug", "FB-00000", DEFAULT_LANG),
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


@mcp.tool(
    description=(
        "Liefert die gerenderte Oberfläche für einen konkreten Fall. Der ui://-Eintrag "
        "bleibt die Kennung der App; dieser Aufruf liefert die Variante für Flow, "
        "Fahrzeug und Sprache."
    )
)
def formular_render(
    listing_id: str, intent: str = "kauf", fahrzeug: str = "", lang: str = "de"
) -> str:
    return _render(intent, fahrzeug or listing_id, listing_id, i18n.normalise(lang))


def render_for(
    intent: str, fahrzeug: str, listing_id: str, lang: str = DEFAULT_LANG
) -> str:
    """Exposed for tests and for the React host, which renders the flow variant."""
    return _render(intent, fahrzeug, listing_id, i18n.normalise(lang))


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
    _serve(mcp, 3001)
