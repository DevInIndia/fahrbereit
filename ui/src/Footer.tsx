import { type Lang, t } from "./i18n";
import { FahrbereitMarke } from "./icons";

interface FooterProps {
  lang: Lang;
  onPersonaClick?: (name: string) => void;
}

const REPO = "https://github.com/DevInIndia/fahrbereit";
const BLOB = `${REPO}/blob/main`;

/**
 * The footer is the evidence column, not decoration.
 *
 * The earlier version listed twelve items of which eight were dead spans styled to
 * look like links, and one of those, "Live Market Price Validation", named a feature
 * that does not exist: it was reverted once Spike C established that Gemini search
 * grounding returns zero quota on a free tier key. A product whose entire claim is
 * auditability cannot advertise a capability its own documentation disproves, and it
 * should not put text that looks clickable in front of a judge who will click it.
 *
 * So every entry below is now one of two things: an action that works, or a link to
 * the file that backs the claim. The middle column is the useful one, because each
 * line names a number the interface shows and points at the code that computes it.
 */
export function Footer({ lang, onPersonaClick }: FooterProps) {
  const de = lang === "de";

  return (
    <footer className="app-footer">
      <div className="app-footer-inner">
        <div className="footer-haupt">
          <div className="footer-marke">
            <FahrbereitMarke size={24} />
            <span className="wordmark">fahrbereit</span>
            <span className="tagline">{t("markeClaim", lang)}</span>
          </div>

          <p className="footer-beschreibung">
            {de
              ? "Die intelligente Fahrzeugsuche für Kauf und Miete in Deutschland. Filterung, Bewertung und Kosten werden in Python berechnet, bevor das Modell spricht. Es liest die Zahlen und erklärt sie; es erzeugt sie nie."
              : "Intelligent vehicle discovery for purchase and rental in Germany. Filtering, scoring and cost are computed in Python before the model speaks. It reads those numbers and explains them; it never produces them."}
          </p>
        </div>

        <div className="footer-links-grid">
          <div className="footer-spalte">
            <div className="eyebrow">{de ? "Ausprobieren" : "Try it"}</div>
            <ul className="footer-liste">
              {onPersonaClick && (
                <>
                  <li>
                    <a
                      href="#katalog"
                      onClick={(e) => {
                        e.preventDefault();
                        onPersonaClick("familie");
                      }}
                    >
                      {de ? "Familie mit zwei Kindern" : "Family with two children"}
                    </a>
                  </li>
                  <li>
                    <a
                      href="#katalog"
                      onClick={(e) => {
                        e.preventDefault();
                        onPersonaClick("pendler");
                      }}
                    >
                      {de ? "Pendler, Automatik" : "Commuter, automatic"}
                    </a>
                  </li>
                  <li>
                    <a
                      href="#katalog"
                      onClick={(e) => {
                        e.preventDefault();
                        onPersonaClick("umzug");
                      }}
                    >
                      {de ? "Umzug am Wochenende, Miete" : "Moving house, rental"}
                    </a>
                  </li>
                </>
              )}
              <li className="footer-notiz">
                {de
                  ? "Diese drei rufen kein Modell auf."
                  : "These three call no model."}
              </li>
            </ul>
          </div>

          <div className="footer-spalte">
            <div className="eyebrow">
              {de ? "Wie die Zahlen entstehen" : "How the numbers are made"}
            </div>
            <ul className="footer-liste">
              <li>
                <a href={`${BLOB}/agent/tools/ranking.py`} target="_blank" rel="noreferrer">
                  {de
                    ? "Harter Filter und Punktebewertung"
                    : "Hard filter and weighted scoring"}
                </a>
              </li>
              <li>
                <a href={`${BLOB}/agent/tools/tco.py`} target="_blank" rel="noreferrer">
                  {de
                    ? "Gesamtkosten und Mietkosten"
                    : "Ownership cost and rental cost"}
                </a>
              </li>
              <li>
                <a
                  href={`${BLOB}/specs/001-fahrbereit-agent/research.md`}
                  target="_blank"
                  rel="noreferrer"
                >
                  {de
                    ? "Kfz-Steuer nach Paragraph 9 KraftStG"
                    : "Vehicle tax, section 9 KraftStG"}
                </a>
              </li>
              <li>
                <a href={`${BLOB}/evals/results.json`} target="_blank" rel="noreferrer">
                  {de
                    ? "Persona-Auswertung, acht Personas"
                    : "Persona evaluation, eight personas"}
                </a>
              </li>
            </ul>
          </div>

          <div className="footer-spalte">
            <div className="eyebrow">{de ? "Das Projekt" : "The project"}</div>
            <ul className="footer-liste">
              <li>
                <a href={REPO} target="_blank" rel="noreferrer" className="footer-repo">
                  {de ? "Quellcode auf GitHub" : "Source on GitHub"}
                </a>
              </li>
              <li>
                <a href={`${BLOB}/README.md`} target="_blank" rel="noreferrer">
                  {de ? "Selbst starten" : "Run it yourself"}
                </a>
              </li>
              <li>
                <a href={`${BLOB}/docs/architecture.md`} target="_blank" rel="noreferrer">
                  {de ? "Architektur" : "Architecture"}
                </a>
              </li>
              <li>
                <a href={`${BLOB}/docs/spike-notes.md`} target="_blank" rel="noreferrer">
                  {de ? "Was nicht funktioniert hat" : "What did not work"}
                </a>
              </li>
            </ul>
          </div>
        </div>

        <div className="footer-unterzeile">
          {/*
            The two things a reader of this footer most needs to know. They belong
            here rather than only in the README, because the footer is where someone
            looks to find out what a product actually is.
          */}
          <p className="footer-offenlegung">
            {de
              ? "Der Marktplatz ist synthetisch: 280 generierte Angebote aus einem festen Seed, kein echter Bestand. Die Bezahlung ist vollständig simuliert; im gesamten Code existiert kein Feld für Kartendaten."
              : "The marketplace is synthetic: 280 generated listings from a committed seed, not real inventory. Payment is fully simulated, and no card input field exists anywhere in the codebase."}
          </p>
          <p className="dim small">
            © 2026 fahrbereit · Amulate Summer Hackathon 2026 · Shashank Chauhan
          </p>
        </div>
      </div>
    </footer>
  );
}
