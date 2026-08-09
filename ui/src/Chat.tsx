/**
 * The conversation. This is the product's front door.
 *
 * The user types free text; the agent interviews, fills the interview record and
 * decides for itself when it has enough to rank. When a turn produces a ranking the
 * A2UI messages come back on the same response and the catalogue surface updates from
 * the agent's result rather than from a persona button.
 */

import { useEffect, useRef, useState } from "react";
import { type Lang, t } from "./i18n";
import { Send } from "./icons";

export type ChatTurn = {
  rolle: "user" | "agent";
  text: string;
  werkzeuge?: string[];
  modellaufrufe?: number;
  gedrosselt?: boolean;
};

type Props = {
  sessionId: string;
  lang: Lang;
  verlauf: ChatTurn[];
  laeuft: boolean;
  onSenden: (text: string) => void;
  onZuruecksetzen: () => void;
};

const VORSCHLAEGE: Record<Lang, string[]> = {
  de: [
    "Ich fahre meine zwei Kinder zur Schule und einmal im Monat 300 km zu meinen Eltern. Budget etwa 25.000 Euro.",
    "Ich pendle jeden Tag 45 km zur Arbeit und möchte Automatik.",
    "Ich brauche für ein Wochenende einen Mietwagen für einen Umzug.",
  ],
  en: [
    "I drive my two children to school and once a month 300 km to my parents. Budget around 25,000 euro.",
    "I commute 45 km to work every day and would like an automatic.",
    "I need a rental car for a weekend to move house.",
  ],
};

export function Chat({
  sessionId,
  lang,
  verlauf,
  laeuft,
  onSenden,
  onZuruecksetzen,
}: Props) {
  const [entwurf, setEntwurf] = useState("");
  const endeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endeRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [verlauf.length, laeuft]);

  function senden() {
    const text = entwurf.trim();
    if (!text || laeuft) return;
    setEntwurf("");
    onSenden(text);
  }

  return (
    <section className="chat">
      <div className="chat-kopf">
        <div className="eyebrow">
          {t("gespraech", lang)}
          <span className="dim"> · {sessionId}</span>
        </div>
        <button className="klein" onClick={onZuruecksetzen} disabled={laeuft}>
          {t("neuStarten", lang)}
        </button>
      </div>

      <div className="chat-verlauf">
        {verlauf.length === 0 && (
          <div className="chat-leer">
            <p className="dim">{t("chatEinleitung", lang)}</p>
            <div className="knopfreihe spalte" style={{ marginTop: 12 }}>
              {VORSCHLAEGE[lang].map((v) => (
                <button key={v} onClick={() => onSenden(v)} disabled={laeuft}>
                  {v}
                </button>
              ))}
            </div>
          </div>
        )}

        {verlauf.map((turn, i) => (
          <div key={i} className={`blase ${turn.rolle}`}>
            <div className="blase-rolle">
              {turn.rolle === "user" ? t("sie", lang) : "fahrbereit"}
            </div>
            <div className="blase-text">{turn.text}</div>
            {turn.werkzeuge && turn.werkzeuge.length > 0 && (
              <div className="werkzeuge">
                {turn.werkzeuge.map((w, k) => (
                  <span key={k} className="tag werkzeug">{w}</span>
                ))}
                {typeof turn.modellaufrufe === "number" && (
                  <span className="dim small">
                    {" "}
                    {turn.modellaufrufe} {t("modellaufrufe", lang)}
                  </span>
                )}
              </div>
            )}
            {turn.gedrosselt && (
              <div className="werkzeuge">
                <span className="tag gedrosselt">{t("gedrosselt", lang)}</span>
              </div>
            )}
          </div>
        ))}

        {laeuft && (
          <div className="blase agent">
            <div className="blase-rolle">fahrbereit</div>
            <div className="blase-text dim">{t("denktNach", lang)}</div>
          </div>
        )}
        <div ref={endeRef} />
      </div>

      <div className="chat-eingabe">
        <textarea
          value={entwurf}
          onChange={(e) => setEntwurf(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              senden();
            }
          }}
          placeholder={t("chatPlatzhalter", lang)}
          rows={2}
          disabled={laeuft}
        />
        <button className="senden" onClick={senden} disabled={laeuft || !entwurf.trim()}>
          <span>{t("senden", lang)}</span>
          <Send size={14} className="ikone" />
        </button>
      </div>
    </section>
  );
}
