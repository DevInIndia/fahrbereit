/**
 * React renderers for the fahrbereit A2UI catalog.
 *
 * These read from the props the agent emits and render them. They compute nothing:
 * no scoring, no filtering, no cost arithmetic. Every number displayed here was
 * produced by the Python ranking engine and arrived over the wire.
 */

import { createContext, useContext, useState } from "react";
import { createCatalog } from "@copilotkit/a2ui-renderer";
import { fahrbereitDefinitions } from "./definitions";
import { type Lang, t } from "../i18n";

/**
 * The renderer's own furniture, table headings and section titles, follows the
 * chosen language. The agent supplies the data and the explanations; the renderer
 * supplies its own labels. Proper nouns in the data are never touched.
 */
export const LangContext = createContext<Lang>("de");
const useLang = () => useContext(LangContext);

const num = (n: number, lang: Lang) =>
  n.toLocaleString(lang === "de" ? "de-DE" : "en-GB");

function Bar({ value, max = 100 }: { value: number; max?: number }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className="bar">
      <div className="bar-fill" style={{ width: `${pct}%` }} />
    </div>
  );
}

export const fahrbereitCatalog = createCatalog(
  fahrbereitDefinitions,
  {
    Spalte: ({ props, children }) => (
      <div className="stack">{props.kinder.map((id) => (
        <div key={id}>{children(id)}</div>
      ))}</div>
    ),

    Kopfzeile: ({ props }) => (
      <header className="kopf">
        <div className="eyebrow">fahrbereit</div>
        <h1>{props.titel}</h1>
        {props.untertitel ? <p className="dim">{props.untertitel}</p> : null}
      </header>
    ),

    FilterBericht: ({ props }) => {
      const lang = useLang();
      return (
      <section className="panel">
        <div className="eyebrow">{t("harteFilter", lang)}</div>
        <table className="tbl">
          <tbody>
            <tr>
              <td>{t("geprueft", lang)}</td>
              <td className="num">{num(props.gesamt, lang)}</td>
            </tr>
            {props.ausgeschlossen.map((row) => (
              <tr key={row.grund}>
                <td className="dim">{t("ausgeschlossenPrefix", lang)}: {row.grund}</td>
                <td className="num dim">−{num(row.anzahl, lang)}</td>
              </tr>
            ))}
            <tr className="total">
              <td>{t("verblieben", lang)}</td>
              <td className="num">{num(props.uebrig, lang)}</td>
            </tr>
          </tbody>
        </table>
      </section>
      );
    },

    GewichtungsPanel: ({ props }) => {
      const lang = useLang();
      return (
      <section className="panel">
        <div className="eyebrow">{t("gewichtungInterview", lang)}</div>
        <table className="tbl">
          <tbody>
            {props.gewichte.map((g) => (
              <tr key={g.name}>
                <td style={{ width: "34%" }}>{g.name}</td>
                <td className="num" style={{ width: "14%" }}>
                  {(g.anteil * 100).toFixed(1)} %
                </td>
                <td><Bar value={g.anteil * 100} max={45} /></td>
              </tr>
            ))}
          </tbody>
        </table>
        {props.hinweis ? <p className="footnote">{props.hinweis}</p> : null}
      </section>
      );
    },

    FahrzeugKarte: ({ props }) => {
      const lang = useLang();
      const [open, setOpen] = useState(props.rang === 1);
      return (
        <article className="karte">
          <div className="karte-kopf" onClick={() => setOpen(!open)}>
            <div className="rang num">{props.rang}</div>
            <div className="karte-titel">
              <h2>{props.bezeichnung}</h2>
              <div className="dim small">{props.kategorie} · {props.eckdaten}</div>
              <div className="dim small">{props.haendler}</div>
            </div>
            <div className="karte-zahlen">
              <div className="preis num">{props.preis}</div>
              <div className="punkte num">{props.punkte.toFixed(1)}</div>
              <Bar value={props.punkte} />
            </div>
            <button className="chev" aria-label={t("begruendungZeigen", lang)}>
              {open ? "−" : "+"}
            </button>
          </div>

          {open && (
            <div className="karte-detail">
              <div className="eyebrow">{t("warumDiesesAuto", lang)}</div>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>{t("thDimension", lang)}</th>
                    <th className="num">{t("thGewicht", lang)}</th>
                    <th className="num">{t("thRang", lang)}</th>
                    <th className="num">{t("thBeitrag", lang)}</th>
                    <th>{t("thBegruendung", lang)}</th>
                  </tr>
                </thead>
                <tbody>
                  {props.dimensionen.map((d) => (
                    <tr key={d.label}>
                      <td>{d.label}</td>
                      <td className="num dim">{d.gewicht.toFixed(2)}</td>
                      <td className="num">{d.wert.toFixed(1)}</td>
                      <td className="num">{d.beitrag.toFixed(2)}</td>
                      <td className="dim small">
                        {d.begruendung}
                        {d.begrenztDurch ? (
                          <span className="limit"> {t("begrenztDurch", lang)} {d.begrenztDurch}</span>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                  <tr className="total">
                    <td>{t("thGesamt", lang)}</td>
                    <td /><td />
                    <td className="num">{props.punkte.toFixed(2)}</td>
                    <td />
                  </tr>
                </tbody>
              </table>

              <p className="footnote">{props.relativHinweis}</p>

              {props.dimensionen.some((d) => d.begrenztDurch) && (
                <>
                  <div className="eyebrow">{t("zusammengesetzt", lang)}</div>
                  {props.dimensionen
                    .filter((d) => d.begrenztDurch)
                    .map((d) => (
                      <table className="tbl" key={d.label}>
                        <tbody>
                          <tr><td colSpan={3} className="dim">{d.label}</td></tr>
                          {[...d.komponenten]
                            .sort((a, b) => a.wert - b.wert)
                            .map((c) => (
                              <tr key={c.name}>
                                <td style={{ paddingLeft: 16 }}>{c.name}</td>
                                <td className="num">{c.wert.toFixed(1)}</td>
                                <td className="dim small">
                                  {c.detail}
                                  {c.name === d.begrenztDurch ? (
                                    <span className="limit"> {t("begrenzend", lang)}</span>
                                  ) : null}
                                </td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    ))}
                </>
              )}

              <div className="eyebrow">{t("ausschlaggebend", lang)}</div>
              <ul className="liste">
                {props.topFaktoren.map((f) => <li key={f}>{f}</li>)}
              </ul>

              {props.schwachstellen.length > 0 && (
                <>
                  <div className="eyebrow">{t("schwaechen", lang)}</div>
                  <ul className="liste schwach">
                    {props.schwachstellen.map((f) => <li key={f}>{f}</li>)}
                  </ul>
                </>
              )}

              {props.tcoGesamt > 0 && (
                <p className="tco">
                  {props.istMiete ? t("kosten", lang) : t("gesamtkosten5j", lang)}:{" "}
                  <strong className="num">{num(props.tcoGesamt, lang)} EUR</strong>
                </p>
              )}

              {props.vergleich ? (
                <p className="footnote">{t("gegenPlatz2", lang)}: {props.vergleich}</p>
              ) : null}
            </div>
          )}
        </article>
      );
    },

    // ---------------------------------------------------- progress surface

    PhasenAnzeige: ({ props }) => (
      <section className="panel">
        <div className="phasen">
          {props.phasen.map((p, i) => (
            <div
              key={p.name}
              className={`phase ${p.aktiv ? "aktiv" : ""} ${p.erledigt ? "erledigt" : ""}`}
            >
              <span className="phase-punkt" />
              <span className="phase-label">{p.label}</span>
              {i < props.phasen.length - 1 && <span className="phase-linie" />}
            </div>
          ))}
        </div>
      </section>
    ),

    SlotCheckliste: ({ props }) => {
      const lang = useLang();
      return (
        <section className="panel">
          <div className="eyebrow">
            {t("interview", lang)}
            <span className="dim">
              {" "}
              {props.gefuellt}/{props.gesamt}
            </span>
          </div>
          <table className="tbl">
            <tbody>
              {props.zeilen.map((z) => (
                <tr key={z.label}>
                  <td className={z.offen ? "dim" : ""} style={{ width: "38%" }}>
                    {z.offen ? "○" : "●"} {z.label}
                  </td>
                  <td className="small">
                    {z.wert || <span className="dim">{t("offen", lang)}</span>}
                  </td>
                  <td style={{ width: 104 }}>
                    {z.herkunft === "inferred" ? (
                      <span className="tag inferred">{t("abgeleitet", lang)}</span>
                    ) : z.herkunft === "default" ? (
                      <span className="tag assumed">{t("angenommen", lang)}</span>
                    ) : z.herkunft === "stated" ? (
                      <span className="tag stated">{t("gesagt", lang)}</span>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {props.hinweis ? <p className="footnote">{props.hinweis}</p> : null}
        </section>
      );
    },

    SuchStatus: ({ props }) => {
      const lang = useLang();
      return (
        <section className="panel">
          <div className="eyebrow">
            {t("harteFilter", lang)}
            {props.aktiv && <span className="puls"> {t("laeuft", lang)}</span>}
          </div>
          {props.gesamt === 0 ? (
            <p className="dim small">{props.hinweis}</p>
          ) : (
            <table className="tbl">
              <tbody>
                <tr>
                  <td>{t("geprueft", lang)}</td>
                  <td className="num">{num(props.gesamt, lang)}</td>
                </tr>
                {props.ausgeschlossen.map((row) => (
                  <tr key={row.grund}>
                    <td className="dim">
                      {t("ausgeschlossenPrefix", lang)}: {row.grund}
                    </td>
                    <td className="num dim">−{num(row.anzahl, lang)}</td>
                  </tr>
                ))}
                <tr className="total">
                  <td>{t("verblieben", lang)}</td>
                  <td className="num">{num(props.uebrig, lang)}</td>
                </tr>
              </tbody>
            </table>
          )}
        </section>
      );
    },

    WerkzeugStrom: ({ props }) => (
      <section className="panel">
        <div className="eyebrow">{props.titel}</div>
        {props.schritte.length === 0 ? (
          <p className="dim small">-</p>
        ) : (
          <ol className="strom">
            {props.schritte.map((s, i) => (
              <li key={i} className={`strom-schritt ${s.status}`}>
                <span className="strom-punkt" />
                <span className="strom-label">{s.label}</span>
                <span className="strom-werkzeug dim">{s.werkzeug}</span>
              </li>
            ))}
          </ol>
        )}
      </section>
    ),
  },
  { catalogId: "fahrbereit/v1", includeBasicCatalog: true },
);
