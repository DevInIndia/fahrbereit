import { type Lang, t } from "./i18n";
import { FahrbereitMarke } from "./icons";

interface FooterProps {
  lang: Lang;
  onPersonaClick?: (name: string) => void;
}

export function Footer({ lang, onPersonaClick }: FooterProps) {
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
            {lang === "de"
              ? "Die intelligente Fahrzeugsuche für Kauf und Miete in Deutschland. Auditierbare Berechnungen, transparente Punktebewertung und Fünf-Jahres-Gesamtkosten ohne versteckte Annahmen."
              : "Intelligent vehicle discovery for purchase and rental in Germany. Auditable calculations, transparent ranking scores, and five-year ownership costs with zero hidden assumptions."}
          </p>
        </div>

        <div className="footer-links-grid">
          <div className="footer-spalte">
            <div className="eyebrow">{lang === "de" ? "Fahrzeuge & Suche" : "Vehicles & Marketplace"}</div>
            <ul className="footer-liste">
              <li>
                <span className="dim">
                  {lang === "de" ? "Gebrauchtwagen-Kauf" : "Pre-owned Car Purchase"}
                </span>
              </li>
              <li>
                <span className="dim">
                  {lang === "de" ? "Wochenend- & Kurzzeitmiete" : "Weekend & Short-term Rental"}
                </span>
              </li>
              <li>
                <span className="dim">
                  {lang === "de" ? "Kombis & Familienautos" : "Estates & Family SUVs"}
                </span>
              </li>
              <li>
                <span className="dim">
                  {lang === "de" ? "Elektro- & Hybrid-Flotten" : "Electric & Hybrid Fleets"}
                </span>
              </li>
            </ul>
          </div>

          <div className="footer-spalte">
            <div className="eyebrow">{lang === "de" ? "Transparenz & Engine" : "Engine & Transparency"}</div>
            <ul className="footer-liste">
              <li>
                <span className="dim">
                  {lang === "de" ? "Auditierbare Punkteberechnung" : "Auditable Scoring Engine"}
                </span>
              </li>
              <li>
                <span className="dim">
                  {lang === "de" ? "5-Jahre Gesamtkosten (TCO)" : "5-Year Total Ownership Cost (TCO)"}
                </span>
              </li>
              <li>
                <span className="dim">
                  {lang === "de" ? "Kfz-Steuer nach §9 KraftStG" : "Motor Vehicle Tax (§9 KraftStG)"}
                </span>
              </li>
              <li>
                <span className="dim">
                  {lang === "de" ? "Live-Marktpreis-Prüfung" : "Live Market Price Validation"}
                </span>
              </li>
            </ul>
          </div>

          <div className="footer-spalte">
            <div className="eyebrow">{lang === "de" ? "Szenarien & Code" : "Presets & Repository"}</div>
            <ul className="footer-liste">
              {onPersonaClick && (
                <>
                  <li>
                    <a href="#katalog" onClick={(e) => { e.preventDefault(); onPersonaClick("familie"); }}>
                      {lang === "de" ? "Familie mit 2 Kindern" : "Family with 2 Kids"}
                    </a>
                  </li>
                  <li>
                    <a href="#katalog" onClick={(e) => { e.preventDefault(); onPersonaClick("pendler"); }}>
                      {lang === "de" ? "Pendler Elektro" : "Electric Commuter"}
                    </a>
                  </li>
                  <li>
                    <a href="#katalog" onClick={(e) => { e.preventDefault(); onPersonaClick("umzug"); }}>
                      {lang === "de" ? "Umzug & Transport" : "Moving House Hire"}
                    </a>
                  </li>
                </>
              )}
              <li>
                <a
                  href="https://github.com/DevInIndia/fahrbereit"
                  target="_blank"
                  rel="noreferrer"
                  style={{ color: "var(--accent)", fontWeight: 500 }}
                >
                  GitHub Repository
                </a>
              </li>
            </ul>
          </div>
        </div>

        <div className="footer-unterzeile">
          <p className="dim small">
            © 2026 fahrbereit · Amulate Summer Hackathon 2026 Submission by Shashank Chauhan.
          </p>
          <p className="dim small">
            {lang === "de" ? "280 generierte Angebote · 100% simulierte Kasse" : "280 synthetic listings · 100% simulated checkout"}
          </p>
        </div>
      </div>
    </footer>
  );
}
