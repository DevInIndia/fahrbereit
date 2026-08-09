import { useCallback, useEffect, useRef, useState } from "react";
import { A2UIProvider, A2UIRenderer, useA2UI } from "@copilotkit/a2ui-renderer";
import { LangContext, fahrbereitCatalog } from "./a2ui/catalog";
import { AppFrame } from "./AppFrame";
import { Chat, type ChatTurn } from "./Chat";
import { IntroLanding } from "./IntroLanding";
import { Footer } from "./Footer";
import { LANGS, type Lang, t } from "./i18n";
import {
  ArrowRight,
  AutoMarke,
  ClipboardList,
  FahrbereitMarke,
  Languages,
  Moon,
  NAV_GROESSE,
  Receipt,
  SlidersHorizontal,
  Sun,
} from "./icons";

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

type Theme = "light" | "dark";

/**
 * Light is the default, and a stored choice wins over it.
 *
 * Read synchronously during the first render rather than in an effect: applying the
 * theme after mount paints the wrong ground first, and that flash is exactly what a
 * theme toggle is supposed to avoid.
 */
function ersteDarstellung(): Theme {
  const gespeichert = localStorage.getItem("fahrbereit.theme");
  return gespeichert === "dark" ? "dark" : "light";
}

function Fortschritt({ rows, lang }: { rows: SlotRow[]; lang: Lang }) {
  if (!rows.length) return null;
  return (
    <section className="panel">
      <div className="eyebrow">{t("profil", lang)}</div>
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
                ) : r.herkunft === "default" ? (
                  <span className="tag assumed">{t("angenommen", lang)}</span>
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
  const [theme, setTheme] = useState<Theme>(ersteDarstellung);
  const surfaceRef = useRef<HTMLDivElement>(null);

  const setSchrittUndScrollen = useCallback((s: Schritt) => {
    setSchritt(s);
    setTimeout(() => {
      surfaceRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 50);
  }, []);

  // The whole theme is CSS variables under [data-theme], so switching is one
  // attribute write. No reload, no re-render of the surfaces, no reflow of the
  // A2UI tree.
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("fahrbereit.theme", theme);
  }, [theme]);

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

  /**
   * Every A2UI message, from the stream or from a persona shortcut, lands here and
   * is applied immediately. No React state in the path, so nothing is batched away.
   *
   * `createSurface` is dropped for a surface that already exists. The server sends a
   * complete, self contained batch every time, which is correct on the wire and is
   * what lets a client connect mid conversation. The renderer, though, treats a
   * second `createSurface` for a live surface as a no-op for the whole batch, so the
   * `updateComponents` behind it was silently discarded: picking a second persona
   * fetched new data, applied none of it, and left the first persona's cards on
   * screen looking like a considered answer.
   *
   * Filtering here rather than on the server keeps the wire format untouched and
   * keeps every batch replayable from cold.
   */
  const flaechen = useRef<Set<string>>(new Set());
  const onSurface = useCallback((msgs: Record<string, unknown>[]) => {
    if (!msgs || !msgs.length) return;

    const anzuwenden = msgs.filter((m) => {
      const erstellen = m.createSurface as { surfaceId?: string } | undefined;
      if (!erstellen?.surfaceId) return true;
      if (flaechen.current.has(erstellen.surfaceId)) return false;
      flaechen.current.add(erstellen.surfaceId);
      return true;
    });

    if (anzuwenden.length) anwenden.current?.(anzuwenden);
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
      <header className="app-header">
        <div className="app-header-inner">
          <div className="marke">
            <FahrbereitMarke size={26} />
            <span>fahrbereit</span>
          </div>
          <div className="marke-claim">{t("markeClaim", lang)}</div>

          <div className="kopf-rechts">
            <div className="segment" role="group" aria-label={t("sprache", lang)}>
              {LANGS.map((l, i) => (
                <button
                  key={l}
                  className={l === lang ? "aktiv" : ""}
                  onClick={() => setLang(l)}
                  aria-pressed={l === lang}
                >
                  {i === 0 && <Languages size={16} className="ikone" />}
                  {l === "de" ? "Deutsch" : "English"}
                </button>
              ))}
            </div>
            <div className="segment" role="group" aria-label={t("darstellung", lang)}>
              {(["light", "dark"] as Theme[]).map((d) => (
                <button
                  key={d}
                  className={d === theme ? "aktiv" : ""}
                  onClick={() => setTheme(d)}
                  aria-pressed={d === theme}
                >
                  {d === "light" ? (
                    <Sun size={16} className="ikone" />
                  ) : (
                    <Moon size={16} className="ikone" />
                  )}
                  {t(d === "light" ? "hell" : "dunkel", lang)}
                </button>
              ))}
            </div>
          </div>
        </div>
      </header>

      <nav className="app-nav">
        <div className="app-nav-inner">
          <div className="nav-gruppe">
            {(
              [
                ["katalog", AutoMarke],
                ["formular", ClipboardList],
                ["kasse", Receipt],
              ] as [Schritt, typeof ClipboardList][]
            ).map(([s, Ikone]) => (
              <button
                key={s}
                className={`nav-tab ${s === schritt ? "aktiv" : ""}`}
                onClick={() => {
                  setSchritt(s);
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }}
                aria-current={s === schritt ? "page" : undefined}
              >
                <Ikone size={NAV_GROESSE} className="ikone" />
                {t(s, lang)}
              </button>
            ))}
          </div>
        </div>
      </nav>

      <div className="shell">
        <details className="drawer">
          <summary>
            <SlidersHorizontal size={NAV_GROESSE} className="ikone" />
            {t("einstellungen", lang)}
          </summary>
          <div className="drawer-inhalt">
            <section className="panel">
              <div className="eyebrow">{t("gewichtung", lang)}</div>
              <div className="knopfreihe spalte">
                <button
                  className={gewichte === null ? "aktiv" : ""}
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
                    className={gewichte && d in gewichte ? "aktiv" : ""}
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
            </section>

            <Fortschritt rows={interview} lang={lang} />

            <section className="panel">
              <div className="eyebrow">{t("ansicht", lang)}</div>
              <p className="footnote" style={{ marginTop: 0 }}>
                {t("einstellungenHinweis", lang)}
              </p>
              <p className="footnote">{t("datenHinweis", lang)}</p>
              <p className="footnote">{t("demoHinweis", lang)}</p>
              {protokoll.length > 0 && (
                <>
                  <div className="eyebrow" style={{ marginTop: 20 }}>
                    {t("bridgeLog", lang)}
                  </div>
                  <ul className="liste small">
                    {protokoll.map((p, i) => <li key={i}>{p}</li>)}
                  </ul>
                </>
              )}
            </section>
          </div>
        </details>

        <main className="haupt">
          {schritt === "katalog" && (
            <>
              <IntroLanding
                lang={lang}
                onStartClick={() => {
                  const chatEl = document.querySelector(".chat");
                  chatEl?.scrollIntoView({ behavior: "smooth", block: "start" });
                  setTimeout(() => {
                    const inputEl = document.querySelector(".chat-eingabe-text, .chat-eingabe textarea") as HTMLTextAreaElement;
                    inputEl?.focus();
                  }, 400);
                }}
                onExploreClick={() => {
                  surfaceRef.current?.scrollIntoView({ behavior: "smooth" });
                }}
              />

              <Chat
                sessionId={sessionId}
                lang={lang}
                verlauf={verlauf}
                laeuft={laeuft}
                onSenden={senden}
                onZuruecksetzen={zuruecksetzen}
              />

              <FortschrittSurface />

              <div ref={surfaceRef} style={{ scrollMarginTop: 20 }}>
                <Katalog lang={lang} />
                <div className="schritt-verbindung-leiste">
                  <button
                    className="schritt-btn primary"
                    onClick={() => {
                      setSchritt("formular");
                      window.scrollTo({ top: 0, behavior: "smooth" });
                    }}
                  >
                    <span>{t("weiterZuFormular", lang)}</span>
                    <ArrowRight size={16} className="ikone" />
                  </button>
                </div>
              </div>
            </>
          )}

          {schritt === "formular" && (
            <div className="schritt-seite">
              <div className="schritt-kopfzeile">
                <div className="eyebrow">{t("schritt2Titel", lang)}</div>
              </div>
              <AppFrame
                title={t("anfrageformular", lang)}
                lang={lang}
                endpoint={`/api/app/formular?listing_id=FB-00001&intent=${intent}&fahrzeug=${fahrzeug}&lang=${lang}`}
                onToolResult={onToolResult}
              />
              <div className="schritt-verbindung-leiste">
                <button
                  className="schritt-btn secondary"
                  onClick={() => {
                    setSchritt("katalog");
                    window.scrollTo({ top: 0, behavior: "smooth" });
                  }}
                >
                  ← {t("zurueckZuKatalog", lang)}
                </button>
                <button
                  className="schritt-btn primary"
                  onClick={() => {
                    setSchritt("kasse");
                    window.scrollTo({ top: 0, behavior: "smooth" });
                  }}
                >
                  <span>{t("weiterZuKasse", lang)}</span>
                  <ArrowRight size={16} className="ikone" />
                </button>
              </div>
            </div>
          )}

          {schritt === "kasse" && (
            <div className="schritt-seite">
              <div className="schritt-kopfzeile">
                <div className="eyebrow">{t("schritt3Titel", lang)}</div>
              </div>
              <AppFrame
                title={t("kasseSimuliert", lang)}
                lang={lang}
                endpoint={`/api/app/kasse?listing_id=FB-00001&intent=${intent}&betrag_eur=${istMiete ? 147 : 21490}&fahrzeug=${fahrzeug}&lang=${lang}`}
                onToolResult={onToolResult}
              />
              <div className="schritt-verbindung-leiste">
                <button
                  className="schritt-btn secondary"
                  onClick={() => {
                    setSchritt("formular");
                    window.scrollTo({ top: 0, behavior: "smooth" });
                  }}
                >
                  ← {t("zurueckZuFormular", lang)}
                </button>
                <button
                  className="schritt-btn primary"
                  onClick={() => {
                    setSchritt("katalog");
                    window.scrollTo({ top: 0, behavior: "smooth" });
                  }}
                >
                  <span>{t("neueSuche", lang)}</span>
                  <ArrowRight size={16} className="ikone" />
                </button>
              </div>
            </div>
          )}
        </main>
      </div>

      <Footer lang={lang} onPersonaClick={(p) => persona(p, null)} />
    </A2UIProvider>
    </LangContext.Provider>
  );
}
