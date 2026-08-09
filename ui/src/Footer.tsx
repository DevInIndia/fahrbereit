import { type Lang, t } from "./i18n";
import { FahrbereitMarke } from "./icons";

export function Footer({ lang }: { lang: Lang }) {
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
              ? "Ein auditierbarer KI-Fahrzeugfinder für Kauf und Miete in Deutschland. Berechnete Gesamtkosten (TCO), Kfz-Steuer nach §9 KraftStG und A2UI v0.9 Generative UI."
              : "An auditable AI car matchmaker for buying and renting in Germany. Computed five-year ownership costs, §9 KraftStG vehicle tax, and A2UI v0.9 Generative UI."}
          </p>
        </div>

        <div className="footer-links-grid">
          <div className="footer-spalte">
            <div className="eyebrow">{lang === "de" ? "Projekt & Repo" : "Project & Code"}</div>
            <ul className="footer-liste">
              <li>
                <a
                  href="https://github.com/DevInIndia/fahrbereit"
                  target="_blank"
                  rel="noreferrer"
                >
                  GitHub Repository
                </a>
              </li>
              <li>
                <a
                  href="https://github.com/DevInIndia/fahrbereit/blob/main/docs/architecture.md"
                  target="_blank"
                  rel="noreferrer"
                >
                  Architecture Specification
                </a>
              </li>
              <li>
                <a
                  href="https://github.com/DevInIndia/fahrbereit/blob/main/README.md"
                  target="_blank"
                  rel="noreferrer"
                >
                  Documentation & README
                </a>
              </li>
            </ul>
          </div>

          <div className="footer-spalte">
            <div className="eyebrow">{lang === "de" ? "Protokolle & Seams" : "Protocols & Engine"}</div>
            <ul className="footer-liste">
              <li>
                <span className="dim">A2UI v0.9 Generative UI</span>
              </li>
              <li>
                <span className="dim">MCP Apps (Formular & Kasse)</span>
              </li>
              <li>
                <span className="dim">LangGraph State Checkpointer</span>
              </li>
              <li>
                <span className="dim">Langfuse OpenTelemetry Tracing</span>
              </li>
            </ul>
          </div>

          <div className="footer-spalte">
            <div className="eyebrow">{lang === "de" ? "Transparenz" : "Transparency"}</div>
            <ul className="footer-liste">
              <li>
                <span className="dim">
                  {lang === "de" ? "280 generierte Listings" : "280 synthetic listings"}
                </span>
              </li>
              <li>
                <span className="dim">
                  {lang === "de" ? "100% simulierte Kasse" : "100% simulated checkout"}
                </span>
              </li>
              <li>
                <span className="dim">
                  {lang === "de" ? "0 Kreditkarteneingaben" : "Zero credit card inputs"}
                </span>
              </li>
            </ul>
          </div>
        </div>

        <div className="footer-unterzeile">
          <p className="dim small">
            © 2026 fahrbereit · Amulate Summer Hackathon 2026 Submission by Shashank Chauhan.
          </p>
        </div>
      </div>
    </footer>
  );
}
