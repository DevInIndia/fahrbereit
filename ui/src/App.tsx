import { useCallback, useEffect, useRef, useState } from "react";
import { A2UIProvider, A2UIRenderer, useA2UI } from "@copilotkit/a2ui-renderer";
import { LangContext, fahrbereitCatalog } from "./a2ui/catalog";
import { AppFrame } from "./AppFrame";
import { Chat, type ChatTurn } from "./Chat";
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
  label?: string;
  wert: string;
  herkunft: string | null;
  bestaetigt: boolean;
  offen: boolean;
};

type Schritt = "katalog" | "formular" | "kasse";

function Katalog({ lang }: { lang: Lang }) {
  return (
    <A2UIRenderer
      surfaceId="fahrbereit-katalog"
      fallback={<p className="dim">{t("wirdAufgebaut", lang)}</p>}
    />
  );
}

/** The live progress surface. Same catalog, its own surface id. */
function FortschrittSurface() {
  return <A2UIRenderer surfaceId="fahrbereit-fortschritt" fallback={null} />;
}

/**
 * Hands `processMessages` out of the provider.
 *
 * Routing A2UI messages through React state loses them: setState replaces rather
 * than appends, and several stream events landing in one batch collapse into the
 * last one, so intermediate progress updates were silently dropped. Applying each
 * message the moment it arrives is the only way an incremental surface stays
 * correct.
 */
function A2UIBridge({ onReady }: { onReady: (apply: (m: Record<string, unknown>[]) => void) => void }) {
  const { processMessages } = useA2UI();
  useEffect(() => {
    onReady(processMessages);
  }, [processMessages, onReady]);
  return null;
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
              <td className={r.offen ? "dim" : ""}>{r.label ?? r.slot}</td>
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

function neueSitzung(): string {
  const vorhanden = sessionStorage.getItem("fahrbereit.session");
  if (vorhanden) return vorhanden;
  const frisch = `s-${Math.random().toString(36).slice(2, 9)}`;
  sessionStorage.setItem("fahrbereit.session", frisch);
  return frisch;
}

export default function App() {
  const [schritt, setSchritt] = useState<Schritt>("katalog");
  const [gewichte, setGewichte] = useState<Record<string, number> | null>(null);
  const [interview, setInterview] = useState<SlotRow[]>([]);
  const [protokoll, setProtokoll] = useState<string[]>([]);
  const [sessionId] = useState(neueSitzung);
  const [verlauf, setVerlauf] = useState<ChatTurn[]>([]);
  const [laeuft, setLaeuft] = useState(false);
  const anwenden = useRef<((m: Record<string, unknown>[]) => void) | null>(null);
  const [istMiete, setIstMiete] = useState(false);
  const [lang, setLang] = useState<Lang>(() => {
    const stored = localStorage.getItem("fahrbereit.lang");
    return stored === "en" || stored === "de" ? stored : "en";
  });

  // English is the default so a reader who does not speak German can audit the
  // ranking without switching first. The choice persists, so a stored preference
  // still wins over this default.
  useEffect(() => {
    localStorage.setItem("fahrbereit.lang", lang);
    document.documentElement.lang = lang;
  }, [lang]);

  const onToolResult = useCallback((tool: string, result: string) => {
    setProtokoll((p) => [...p, `${tool} -> ${result}`.slice(0, 240)]);
  }, []);

  // Every A2UI message, from the stream or from a persona shortcut, lands here and
  // is applied immediately. No React state in the path, so nothing is batched away.
  const onSurface = useCallback((msgs: Record<string, unknown>[]) => {
    if (msgs && msgs.length) anwenden.current?.(msgs);
  }, []);

  const bridgeBereit = useCallback((apply: (m: Record<string, unknown>[]) => void) => {
    anwenden.current = apply;
  }, []);

  // A conversational turn, streamed. Each event carries incremental A2UI updates
  // that are applied the moment they arrive, which is what makes the progress
  // surface live rather than a summary printed afterwards.
  const senden = useCallback(
    async (text: string) => {
      setVerlauf((v) => [...v, { rolle: "user", text }]);
      setLaeuft(true);
      setSchritt("katalog");
      try {
        const res = await fetch("/api/chat/stream", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sessionId, nachricht: text, lang }),
        });
        if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let puffer = "";

        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          puffer += decoder.decode(value, { stream: true });

          // Server sent events are separated by a blank line.
          let grenze;
          while ((grenze = puffer.indexOf("\n\n")) !== -1) {
            const roh = puffer.slice(0, grenze);
            puffer = puffer.slice(grenze + 2);

            const zeilen = roh.split("\n");
            const event = zeilen.find((z) => z.startsWith("event: "))?.slice(7) ?? "";
            const daten = zeilen.find((z) => z.startsWith("data: "))?.slice(6) ?? "{}";
            let nutzlast: Record<string, unknown>;
            try {
              nutzlast = JSON.parse(daten);
            } catch {
              continue;
            }

            if (event === "a2ui" || event === "katalog") {
              onSurface(nutzlast.messages as Record<string, unknown>[]);
            } else if (event === "fertig") {
              setVerlauf((v) => [
                ...v,
                {
                  rolle: "agent",
                  text: (nutzlast.antwort as string) || "...",
                  werkzeuge: nutzlast.werkzeuge as string[],
                  modellaufrufe: nutzlast.modellaufrufe as number,
                  gedrosselt: nutzlast.gedrosselt as boolean,
                },
              ]);
            }
          }
        }
      } catch (e) {
        setVerlauf((v) => [
          ...v,
          { rolle: "agent", text: `${t("backendWeg", lang)}: ${e}` },
        ]);
      } finally {
        setLaeuft(false);
      }
    },
    [sessionId, lang, onSurface],
  );

  const zuruecksetzen = useCallback(async () => {
    setVerlauf([]);
    setInterview([]);
    await fetch("/api/chat/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, nachricht: "-", lang }),
    });
  }, [sessionId, lang]);

  // The persona shortcut. Bypasses the model entirely, so it still works when the
  // daily quota is gone, which is the point of keeping it.
  const persona = useCallback(
    async (name: string, gew: Record<string, number> | null) => {
      setIstMiete(name === "umzug");
      const res = await fetch("/api/surface/katalog", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ persona: name, gewichte: gew, limit: 6, lang }),
      });
      const data = await res.json();
      onSurface(data.messages);
      setInterview(data.interview);
      setSchritt("katalog");
    },
    [lang, onSurface],
  );

  const [letztePersona, setLetztePersona] = useState<string | null>(null);
  const intent = istMiete ? "miete" : "kauf";
  const fahrzeug = encodeURIComponent(t("ausgewaehltesFahrzeug", lang));

  return (
    <LangContext.Provider value={lang}>
    <A2UIProvider catalog={fahrbereitCatalog}>
      <A2UIBridge onReady={bridgeBereit} />
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

          <div className="eyebrow" style={{ marginTop: 22 }}>
            {t("demoAbkuerzung", lang)}
          </div>
          <div className="knopfreihe">
            {["familie", "pendler", "umzug"].map((p) => (
              <button
                key={p}
                className={p === letztePersona ? "aktiv" : ""}
                onClick={() => {
                  setLetztePersona(p);
                  setGewichte(null);
                  persona(p, null);
                }}
              >
                {t(`persona.${p}`, lang)}
              </button>
            ))}
          </div>
          <p className="footnote">{t("demoHinweis", lang)}</p>

          <div className="eyebrow" style={{ marginTop: 22 }}>{t("gewichtung", lang)}</div>
          <div className="knopfreihe spalte">
            <button
              onClick={() => {
                setGewichte(null);
                persona(letztePersona ?? "familie", null);
              }}
            >
              {t("zuruecksetzen", lang)}
            </button>
            {DIMENSIONEN.map((d) => (
              <button
                key={d}
                onClick={() => {
                  setGewichte({ [d]: 1 });
                  persona(letztePersona ?? "familie", { [d]: 1 });
                }}
              >
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
          <Chat
            sessionId={sessionId}
            lang={lang}
            verlauf={verlauf}
            laeuft={laeuft}
            onSenden={senden}
            onZuruecksetzen={zuruecksetzen}
          />

          <FortschrittSurface />

          {schritt === "katalog" && <Katalog lang={lang} />}
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
