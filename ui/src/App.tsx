import { useCallback, useEffect, useState } from "react";
import { A2UIProvider, A2UIRenderer, useA2UI } from "@copilotkit/a2ui-renderer";
import { fahrbereitCatalog } from "./a2ui/catalog";
import { AppFrame } from "./AppFrame";

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
  onInterview,
}: {
  persona: string;
  gewichte: Record<string, number> | null;
  onInterview: (rows: SlotRow[]) => void;
}) {
  const { processMessages, clearSurfaces } = useA2UI();
  const [fehler, setFehler] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/surface/katalog", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ persona, gewichte, limit: 6 }),
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data) => {
        if (cancelled) return;
        clearSurfaces();
        // The agent side speaks A2UI. This is the whole integration.
        processMessages(data.messages);
        onInterview(data.interview);
        setFehler(null);
      })
      .catch((e) => !cancelled && setFehler(String(e)));
    return () => {
      cancelled = true;
    };
  }, [persona, gewichte, processMessages, clearSurfaces, onInterview]);

  if (fehler) return <p className="err">Backend nicht erreichbar: {fehler}</p>;
  return (
    <A2UIRenderer
      surfaceId="fahrbereit-katalog"
      fallback={<p className="dim">Oberfläche wird aufgebaut...</p>}
    />
  );
}

function Fortschritt({ rows }: { rows: SlotRow[] }) {
  if (!rows.length) return null;
  return (
    <section className="panel">
      <div className="eyebrow">Interview</div>
      <table className="tbl">
        <tbody>
          {rows.map((r) => (
            <tr key={r.slot}>
              <td className={r.offen ? "dim" : ""}>{r.slot}</td>
              <td className="small">{r.wert || <span className="dim">offen</span>}</td>
              <td style={{ width: 96 }}>
                {r.herkunft === "inferred" ? (
                  <span className="tag inferred">abgeleitet</span>
                ) : r.herkunft === "stated" ? (
                  <span className="tag stated">gesagt</span>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="footnote">
        Abgeleitete Werte sind markiert und vom Nutzer korrigierbar.
      </p>
    </section>
  );
}

export default function App() {
  const [persona, setPersona] = useState("familie");
  const [schritt, setSchritt] = useState<Schritt>("katalog");
  const [gewichte, setGewichte] = useState<Record<string, number> | null>(null);
  const [interview, setInterview] = useState<SlotRow[]>([]);
  const [protokoll, setProtokoll] = useState<string[]>([]);

  const onInterview = useCallback((rows: SlotRow[]) => setInterview(rows), []);
  const onToolResult = useCallback((tool: string, result: string) => {
    setProtokoll((p) => [...p, `${tool} -> ${result}`.slice(0, 240)]);
  }, []);

  const istMiete = persona === "umzug";
  const intent = istMiete ? "miete" : "kauf";

  return (
    <A2UIProvider catalog={fahrbereitCatalog}>
      <div className="shell">
        <aside className="seite">
          <div className="eyebrow">Persona</div>
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

          <div className="eyebrow" style={{ marginTop: 22 }}>Gewichtung</div>
          <div className="knopfreihe spalte">
            <button onClick={() => setGewichte(null)}>zurücksetzen</button>
            {DIMENSIONEN.map((d) => (
              <button key={d} onClick={() => setGewichte({ [d]: 1 })}>
                nur {d}
              </button>
            ))}
          </div>
          <p className="footnote">
            Die Gewichtung gehört dem Nutzer. Die Voreinstellung ist ein Startpunkt,
            kein Urteil.
          </p>

          <div className="eyebrow" style={{ marginTop: 22 }}>Ablauf</div>
          <div className="knopfreihe spalte">
            {(["katalog", "formular", "kasse"] as Schritt[]).map((s) => (
              <button
                key={s}
                className={s === schritt ? "aktiv" : ""}
                onClick={() => setSchritt(s)}
              >
                {s}
              </button>
            ))}
          </div>

          <Fortschritt rows={interview} />

          {protokoll.length > 0 && (
            <section className="panel">
              <div className="eyebrow">Bridge-Protokoll</div>
              <ul className="liste small">
                {protokoll.map((p, i) => <li key={i}>{p}</li>)}
              </ul>
            </section>
          )}
        </aside>

        <main className="haupt">
          {schritt === "katalog" && (
            <Katalog persona={persona} gewichte={gewichte} onInterview={onInterview} />
          )}
          {schritt === "formular" && (
            <AppFrame
              title="Anfrageformular"
              endpoint={`/api/app/formular?listing_id=FB-00001&intent=${intent}&fahrzeug=Ausgew%C3%A4hltes%20Fahrzeug`}
              onToolResult={onToolResult}
            />
          )}
          {schritt === "kasse" && (
            <AppFrame
              title="Kasse, simuliert"
              endpoint={`/api/app/kasse?listing_id=FB-00001&intent=${intent}&betrag_eur=${istMiete ? 147 : 21490}&fahrzeug=Ausgew%C3%A4hltes%20Fahrzeug`}
              onToolResult={onToolResult}
            />
          )}
        </main>
      </div>
    </A2UIProvider>
  );
}

