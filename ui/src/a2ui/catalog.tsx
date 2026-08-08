/**
 * React renderers for the fahrbereit A2UI catalog.
 *
 * These read from the props the agent emits and render them. They compute nothing:
 * no scoring, no filtering, no cost arithmetic. Every number displayed here was
 * produced by the Python ranking engine and arrived over the wire.
 */

import { useState } from "react";
import { createCatalog } from "@copilotkit/a2ui-renderer";
import { fahrbereitDefinitions } from "./definitions";

const de = (n: number) => n.toLocaleString("de-DE");

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

    FilterBericht: ({ props }) => (
      <section className="panel">
        <div className="eyebrow">Harte Filter</div>
        <table className="tbl">
          <tbody>
            <tr>
              <td>Geprüfte Angebote</td>
              <td className="num">{de(props.gesamt)}</td>
            </tr>
            {props.ausgeschlossen.map((row) => (
              <tr key={row.grund}>
                <td className="dim">ausgeschlossen: {row.grund}</td>
                <td className="num dim">−{de(row.anzahl)}</td>
              </tr>
            ))}
            <tr className="total">
              <td>Verblieben</td>
              <td className="num">{de(props.uebrig)}</td>
            </tr>
          </tbody>
        </table>
      </section>
    ),

    GewichtungsPanel: ({ props }) => (
      <section className="panel">
        <div className="eyebrow">Gewichtung aus dem Interview</div>
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
    ),

    FahrzeugKarte: ({ props }) => {
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
            <button className="chev" aria-label="Begründung anzeigen">
              {open ? "−" : "+"}
            </button>
          </div>

          {open && (
            <div className="karte-detail">
              <div className="eyebrow">Warum dieses Auto</div>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Dimension</th>
                    <th className="num">Gewicht</th>
                    <th className="num">Rang</th>
                    <th className="num">Beitrag</th>
                    <th>Begründung</th>
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
                          <span className="limit"> begrenzt durch {d.begrenztDurch}</span>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                  <tr className="total">
                    <td>Gesamt</td>
                    <td /><td />
                    <td className="num">{props.punkte.toFixed(2)}</td>
                    <td />
                  </tr>
                </tbody>
              </table>

              <p className="footnote">{props.relativHinweis}</p>

              {props.dimensionen.some((d) => d.begrenztDurch) && (
                <>
                  <div className="eyebrow">Zusammengesetzte Dimensionen</div>
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
                                    <span className="limit"> begrenzend</span>
                                  ) : null}
                                </td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    ))}
                </>
              )}

              <div className="eyebrow">Ausschlaggebend</div>
              <ul className="liste">
                {props.topFaktoren.map((f) => <li key={f}>{f}</li>)}
              </ul>

              {props.schwachstellen.length > 0 && (
                <>
                  <div className="eyebrow">Schwächen</div>
                  <ul className="liste schwach">
                    {props.schwachstellen.map((f) => <li key={f}>{f}</li>)}
                  </ul>
                </>
              )}

              {props.tcoGesamt > 0 && (
                <p className="tco">
                  {props.istMiete ? "Kosten" : "Gesamtkosten über fünf Jahre"}:{" "}
                  <strong className="num">{de(props.tcoGesamt)} EUR</strong>
                </p>
              )}

              {props.vergleich ? (
                <p className="footnote">Gegen Platz 2: {props.vergleich}</p>
              ) : null}
            </div>
          )}
        </article>
      );
    },
  },
  { catalogId: "fahrbereit/v1", includeBasicCatalog: true },
);
