import { useCallback, useEffect, useState } from "react";
import { A2UIProvider, A2UIRenderer, useA2UI } from "@copilotkit/a2ui-renderer";
import { LangContext, fahrbereitCatalog } from "./a2ui/catalog";
import { AppFrame } from "./AppFrame";
import { LANGS, type Lang, t } from "./i18n";

const DIMENSIONEN = [
  "preis_spielraum",
  "gesamtkosten",
  "alter_laufleistung",
  "einsatzzweck",
  "zustand",
  "entfernung",
] as const;

type SlotRow = {
  slot: string;
  wert: string;
  herkunft: string | null;
  bestaetigt: boolean;
  offen: boolean;
};

type Schritt = "katalog" | "formular" | "kasse";

function Katalog({
  persona,
  gewichte,
  lang,
  onInterview,
}: {
  persona: string;
  gewichte: Record<string, number> | null;
  lang: Lang;
  onInterview: (rows: SlotRow[]) => void;
}) {
  const { processMessages, clearSurfaces } = useA2UI();
  const [fehler, setFehler] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/surface/katalog", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ persona, gewichte, limit: 6, lang }),
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data) => {
        if (cancelled) return;
        clearSurfaces();
        // The server side speaks A2UI. This is the whole integration.
        processMessages(data.messages);
        onInterview(data.interview);
        setFehler(null);
      })
      .catch((e) => !cancelled && setFehler(String(e)));
    return () => {
      cancelled = true;
    };
  }, [persona, gewichte, lang, processMessages, clearSurfaces, onInterview]);

  if (fehler) return <p className="err">{t("backendWeg", lang)}: {fehler}</p>;
  return (
    <A2UIRenderer
      surfaceId="fahrbereit-katalog"
      fallback={<p className="dim">{t("wirdAufgebaut", lang)}</p>}
    />
  );
}

function Fortschritt({ rows, lang }: { rows: SlotRow[]; lang: Lang }) {
  if (!rows.length) return null;
  return (
    <section className="panel">
      <div className="eyebrow">{t("interview", lang)}</div>
      <table className="tbl">
        <tbody>
          {rows.map((r) => (
            <tr key={r.slot}>
              <td className={r.offen ? "dim" : ""}>{r.slot}</td>
              <td className="small">
                {r.wert || <span className="dim">{t("offen", lang)}</span>}
              </td>
              <td style={{ width: 104 }}>
                {r.herkunft === "inferred" ? (
                  <span className="tag inferred">{t("abgeleitet", lang)}</span>
                ) : r.herkunft === "stated" ? (
                  <span className="tag stated">{t("gesagt", lang)}</span>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="footnote">{t("interviewHinweis", lang)}</p>
    </section>
  );
}

export default function App() {
  const [persona, setPersona] = useState("familie");
  const [schritt, setSchritt] = useState<Schritt>("katalog");
  const [gewichte, setGewichte] = useState<Record<string, number> | null>(null);
  const [interview, setInterview] = useState<SlotRow[]>([]);
  const [protokoll, setProtokoll] = useState<string[]>([]);
  const [lang, setLang] = useState<Lang>(() => {
    const stored = localStorage.getItem("fahrbereit.lang");
    return stored === "en" || stored === "de" ? stored : "de";
  });

  // German is the default because the product is German market facing. The choice
  // persists so a reader who switches once does not have to switch again.
  useEffect(() => {
    localStorage.setItem("fahrbereit.lang", lang);
    document.documentElement.lang = lang;
  }, [lang]);

  const onInterview = useCallback((rows: SlotRow[]) => setInterview(rows), []);
  const onToolResult = useCallback((tool: string, result: string) => {
    setProtokoll((p) => [...p, `${tool} -> ${result}`.slice(0, 240)]);
  }, []);

  const istMiete = persona === "umzug";
  const intent = istMiete ? "miete" : "kauf";
  const fahrzeug = encodeURIComponent(t("ausgewaehltesFahrzeug", lang));

  return (
    <LangContext.Provider value={lang}>
    <A2UIProvider catalog={fahrbereitCatalog}>
      <div className="shell">
        <aside className="seite">
          <div className="eyebrow">{t("sprache", lang)}</div>
          <div className="knopfreihe">
            {LANGS.map((l) => (
              <button
                key={l}
                className={l === lang ? "aktiv" : ""}
                onClick={() => setLang(l)}
                aria-pressed={l === lang}
              >
                {l === "de" ? "Deutsch" : "English"}
              </button>
            ))}
          </div>

          <div className="eyebrow" style={{ marginTop: 22 }}>{t("persona", lang)}</div>
          <div className="knopfreihe">
            {["familie", "pendler", "umzug"].map((p) => (
              <button
                key={p}
                className={p === persona ? "aktiv" : ""}
                onClick={() => {
                  setPersona(p);
                  setGewichte(null);
                  setSchritt("katalog");
                }}
              >
                {p}
              </button>
            ))}
          </div>

          <div className="eyebrow" style={{ marginTop: 22 }}>{t("gewichtung", lang)}</div>
          <div className="knopfreihe spalte">
            <button onClick={() => setGewichte(null)}>{t("zuruecksetzen", lang)}</button>
            {DIMENSIONEN.map((d) => (
              <button key={d} onClick={() => setGewichte({ [d]: 1 })}>
                {t("nur", lang)} {t(`dim.${d}`, lang)}
              </button>
            ))}
          </div>
          <p className="footnote">{t("gewichtungHinweis", lang)}</p>

          <div className="eyebrow" style={{ marginTop: 22 }}>{t("ablauf", lang)}</div>
          <div className="knopfreihe spalte">
            {(["katalog", "formular", "kasse"] as Schritt[]).map((s) => (
              <button
                key={s}
                className={s === schritt ? "aktiv" : ""}
                onClick={() => setSchritt(s)}
              >
                {t(s, lang)}
              </button>
            ))}
          </div>

          <Fortschritt rows={interview} lang={lang} />

          {protokoll.length > 0 && (
            <section className="panel">
              <div className="eyebrow">{t("bridgeLog", lang)}</div>
              <ul className="liste small">
                {protokoll.map((p, i) => <li key={i}>{p}</li>)}
              </ul>
            </section>
          )}
        </aside>

        <main className="haupt">
          {schritt === "katalog" && (
            <Katalog
              persona={persona}
              gewichte={gewichte}
              lang={lang}
              onInterview={onInterview}
            />
          )}
          {schritt === "formular" && (
            <AppFrame
              title={t("anfrageformular", lang)}
              lang={lang}
              endpoint={`/api/app/formular?listing_id=FB-00001&intent=${intent}&fahrzeug=${fahrzeug}&lang=${lang}`}
              onToolResult={onToolResult}
            />
          )}
          {schritt === "kasse" && (
            <AppFrame
              title={t("kasseSimuliert", lang)}
              lang={lang}
              endpoint={`/api/app/kasse?listing_id=FB-00001&intent=${intent}&betrag_eur=${istMiete ? 147 : 21490}&fahrzeug=${fahrzeug}&lang=${lang}`}
              onToolResult={onToolResult}
            />
          )}
        </main>
      </div>
    </A2UIProvider>
    </LangContext.Provider>
  );
}
