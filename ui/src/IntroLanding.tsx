import { useState, useEffect } from "react";
import { type Lang } from "./i18n";
import { ArrowRight, LayoutGrid, ShieldCheck, Cpu } from "./icons";

interface IntroLandingProps {
  lang: Lang;
  onStartClick: () => void;
  onExploreClick: () => void;
}

const HERO_IMAGES = [
  {
    url: "/hero/hero-grille.png",
    captionDe: "Sportliche Performance & Dynamik",
    captionEn: "Performance & Illuminated Design",
  },
  {
    url: "/hero/hero-motion.jpg",
    captionDe: "Reale Effizienz auf deutschen Straßen",
    captionEn: "Real-World Efficiency on German Roads",
  },
  {
    url: "/hero/hero-sedan.png",
    captionDe: "Nachhaltige Mobilität & Transparenz",
    captionEn: "Sustainable Mobility & Transparent Ownership",
  },
];

export function IntroLanding({ lang, onStartClick, onExploreClick }: IntroLandingProps) {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setIndex((i) => (i + 1) % HERO_IMAGES.length);
    }, 8500);
    return () => clearInterval(timer);
  }, []);

  return (
    <section className="intro-hero-section">
      <div className="intro-hero-bg">
        {HERO_IMAGES.map((img, i) => (
          <div
            key={img.url}
            className={`intro-slide ${i === index ? "aktiv" : ""}`}
            style={{ backgroundImage: `url(${img.url})` }}
          />
        ))}
        <div className="intro-overlay" />
      </div>

      <div className="intro-hero-content">
        <h1 className="intro-titel">
          {lang === "de"
            ? "Perfekte Autos finden. Transparent & Nachvollziehbar."
            : "The Future of Vehicle Discovery."}
        </h1>

        <p className="intro-beschreibung">
          {lang === "de"
            ? "Fahrbereit verbindet natürliche Konversation mit einer auditierbaren Python-Berechnungsengine. Gesamtkosten (TCO) und Kfz-Steuer nach §9 KraftStG transparent berechnet."
            : "Fahrbereit pairs natural conversational AI with a deterministic Python engine. Hard filtering, weighted scoring, and five-year German ownership costs computed before narration."}
        </p>

        <div className="intro-knopfreihe">
          <button className="intro-btn primary" onClick={onStartClick}>
            {lang === "de" ? "Jetzt Chat starten" : "Start Live AI Interview"}
            <ArrowRight size={16} className="ikone" />
          </button>
          <button className="intro-btn secondary" onClick={onExploreClick}>
            {lang === "de" ? "Katalog durchsuchen" : "Explore Ranked Marketplace"}
          </button>
        </div>

        <div className="intro-features">
          <div className="intro-feature-item">
            <ShieldCheck size={18} className="feature-ikone" />
            <div>
              <strong>{lang === "de" ? "Auditierbare Mathematik" : "Auditable Engine"}</strong>
              <p>{lang === "de" ? "Kein Halluzinieren von Preisen" : "Python-calculated scores & TCO"}</p>
            </div>
          </div>

          <div className="intro-feature-item">
            <Cpu size={18} className="feature-ikone" />
            <div>
              <strong>{lang === "de" ? "Integrierte MCP Apps" : "Embedded MCP Apps"}</strong>
              <p>{lang === "de" ? "Formular & Kasse direkt im Chat" : "Form filling & mock checkout inside chat"}</p>
            </div>
          </div>

          <div className="intro-feature-item">
            <LayoutGrid size={18} className="feature-ikone" />
            <div>
              <strong>{lang === "de" ? "Generative UI (A2UI)" : "Generative UI (A2UI)"}</strong>
              <p>{lang === "de" ? "Echtzeit SSE Streaming-Fortschritt" : "Live SSE progress streaming surface"}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="intro-dots">
        {HERO_IMAGES.map((_, i) => (
          <button
            key={i}
            className={`dot ${i === index ? "aktiv" : ""}`}
            onClick={() => setIndex(i)}
            aria-label={`Slide ${i + 1}`}
          />
        ))}
      </div>
    </section>
  );
}
