/**
 * Interface chrome, in German and English.
 *
 * Only the shell lives here: sidebar labels, buttons, panel headings. Everything
 * inside the A2UI surface and inside the MCP App iframes is translated on the server,
 * because that is where the text is generated. The client sends `lang` and renders
 * what comes back.
 *
 * Never translated in either direction: manufacturer, model and variant names, dealer
 * and operator names, place names, listing ids, and the token SIMULATION.
 */

export type Lang = "de" | "en";

export const LANGS: Lang[] = ["de", "en"];

const STRINGS: Record<string, Record<Lang, string>> = {
  persona: { de: "Persona", en: "Persona" },
  gewichtung: { de: "Gewichtung", en: "Weighting" },
  ablauf: { de: "Ablauf", en: "Flow" },
  sprache: { de: "Sprache", en: "Language" },
  interview: { de: "Interview", en: "Interview" },
  bridgeLog: { de: "Bridge-Protokoll", en: "Bridge log" },

  katalog: { de: "Katalog", en: "Catalogue" },
  formular: { de: "Formular", en: "Form" },
  kasse: { de: "Kasse", en: "Checkout" },

  zuruecksetzen: { de: "zurücksetzen", en: "reset" },
  nur: { de: "nur", en: "only" },
  offen: { de: "offen", en: "open" },
  gesagt: { de: "gesagt", en: "stated" },
  abgeleitet: { de: "abgeleitet", en: "inferred" },
  angenommen: { de: "angenommen", en: "assumed" },

  gewichtungHinweis: {
    de: "Die Gewichtung gehört dem Nutzer. Die Voreinstellung ist ein Startpunkt, kein Urteil.",
    en: "The weighting belongs to the user. The default is a starting position, not a verdict.",
  },
  interviewHinweis: {
    de:
      "Gesagt kommt vom Nutzer, abgeleitet hat der Agent daraus geschlossen, " +
      "angenommen hat niemand gewählt. Alle drei sind korrigierbar.",
    en:
      "Stated came from the user, inferred is what the agent concluded from it, " +
      "assumed was chosen by nobody. All three can be corrected.",
  },
  datenHinweis: {
    de: "Synthetischer Marktplatz: 280 generierte Angebote.",
    en: "Synthetic marketplace: 280 generated listings.",
  },

  wirdAufgebaut: { de: "Oberfläche wird aufgebaut...", en: "Building the surface..." },
  wirdGeladen: { de: "Wird geladen...", en: "Loading..." },
  backendWeg: { de: "Backend nicht erreichbar", en: "Backend unreachable" },
  ladenFehlgeschlagen: {
    de: "Konnte die Oberfläche nicht laden",
    en: "Could not load the surface",
  },

  anfrageformular: { de: "Anfrageformular", en: "Enquiry form" },
  kasseSimuliert: { de: "Kasse, simuliert", en: "Checkout, simulated" },
  ausgewaehltesFahrzeug: { de: "Ausgewähltes Fahrzeug", en: "Selected vehicle" },

  // Dimension keys are shown as-is in the sidebar buttons; these give them a
  // readable form that matches what the server sends inside the surface.
  "dim.preis_spielraum": { de: "Preisspielraum", en: "Price headroom" },
  "dim.gesamtkosten": { de: "Gesamtkosten", en: "Total cost" },
  "dim.alter_laufleistung": { de: "Alter und Laufleistung", en: "Age and mileage" },
  "dim.einsatzzweck": { de: "Einsatzzweck", en: "Fitness for purpose" },
  "dim.zustand": { de: "Zustand", en: "Condition" },
  "dim.entfernung": { de: "Entfernung", en: "Distance" },

  // Renderer furniture inside the A2UI surface.
  harteFilter: { de: "Harte Filter", en: "Hard filters" },
  geprueft: { de: "Geprüfte Angebote", en: "Listings checked" },
  ausgeschlossenPrefix: { de: "ausgeschlossen", en: "excluded" },
  verblieben: { de: "Verblieben", en: "Remaining" },
  gewichtungInterview: {
    de: "Gewichtung aus dem Interview",
    en: "Weighting from the interview",
  },
  warumDiesesAuto: { de: "Warum dieses Auto", en: "Why this car" },
  begruendungZeigen: { de: "Begründung anzeigen", en: "Show reasoning" },
  thDimension: { de: "Dimension", en: "Dimension" },
  thGewicht: { de: "Gewicht", en: "Weight" },
  thRang: { de: "Rang", en: "Rank" },
  thBeitrag: { de: "Beitrag", en: "Contribution" },
  thBegruendung: { de: "Begründung", en: "Basis" },
  thGesamt: { de: "Gesamt", en: "Total" },
  begrenztDurch: { de: "begrenzt durch", en: "limited by" },
  begrenzend: { de: "begrenzend", en: "limiting" },
  zusammengesetzt: { de: "Zusammengesetzte Dimensionen", en: "Composite dimensions" },
  ausschlaggebend: { de: "Ausschlaggebend", en: "Decisive factors" },
  schwaechen: { de: "Schwächen", en: "Weaknesses" },
  kosten: { de: "Kosten", en: "Cost" },
  gesamtkosten5j: {
    de: "Gesamtkosten über fünf Jahre",
    en: "Total cost over five years",
  },
  gegenPlatz2: { de: "Gegen Platz 2", en: "Against runner-up" },

  // Conversation.
  gespraech: { de: "Gespräch", en: "Conversation" },
  neuStarten: { de: "neu starten", en: "restart" },
  senden: { de: "Senden", en: "Send" },
  sie: { de: "Sie", en: "You" },
  denktNach: { de: "denkt nach...", en: "thinking..." },
  modellaufrufe: { de: "Modellaufrufe", en: "model calls" },
  gedrosselt: { de: "Kontingent erschöpft", en: "quota exhausted" },
  chatPlatzhalter: {
    de: "Beschreiben Sie, wofür Sie ein Auto brauchen. Enter sendet.",
    en: "Describe what you need a car for. Enter sends.",
  },
  chatEinleitung: {
    de: "Schreiben Sie in eigenen Worten, wofür Sie ein Auto brauchen. Der Agent stellt Rückfragen, leitet ab, was er ableiten kann, und erstellt dann eine Rangfolge. Oder wählen Sie einen Einstieg:",
    en: "Describe in your own words what you need a car for. The agent asks follow-up questions, infers what it can, and then produces a ranking. Or pick a starting point:",
  },
  demoAbkuerzung: { de: "Demo-Abkürzung", en: "Demo shortcut" },
  demoHinweis: {
    de: "Die Personen umgehen das Modell. Sie funktionieren auch, wenn das Kontingent erschöpft ist.",
    en: "The personas bypass the model. They keep working when the quota is exhausted.",
  },

  // Persona shortcuts. The keys are identifiers; these are what a user reads.
  "persona.familie": { de: "Familie", en: "Family" },
  "persona.pendler": { de: "Pendler", en: "Commuter" },
  "persona.umzug": { de: "Umzug", en: "Moving house" },

  laeuft: { de: "läuft", en: "running" },
  agentFortschritt: { de: "Agent", en: "Agent" },
};

export function t(key: string, lang: Lang): string {
  return STRINGS[key]?.[lang] ?? key;
}
