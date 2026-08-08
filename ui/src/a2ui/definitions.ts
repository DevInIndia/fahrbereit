/**
 * A2UI component catalog: the contract between the agent and this interface.
 *
 * Platform agnostic on purpose. These Zod schemas describe what the agent may emit;
 * the React renderers in catalog.tsx are a separate concern. The agent never sends
 * markup, only component names and typed props, which is the difference between a
 * dynamic surface and a string of HTML.
 */

import { z } from "zod";
import type { CatalogDefinitions } from "@copilotkit/a2ui-renderer";

const komponente = z.object({
  name: z.string(),
  wert: z.number(),
  detail: z.string(),
});

const dimension = z.object({
  label: z.string(),
  wert: z.number(),
  gewicht: z.number(),
  beitrag: z.number(),
  begruendung: z.string(),
  begrenztDurch: z.string().optional().default(""),
  komponenten: z.array(komponente).optional().default([]),
});

export const fahrbereitDefinitions = {
  Spalte: {
    description: "Senkrechter Stapel von Kindkomponenten.",
    props: z.object({ kinder: z.array(z.string()) }),
  },

  Kopfzeile: {
    description: "Überschrift der Oberfläche mit erklärender Unterzeile.",
    props: z.object({ titel: z.string(), untertitel: z.string().optional().default("") }),
  },

  FilterBericht: {
    description:
      "Ergebnis des harten Filters: geprüfte Angebote, verbliebene Angebote und " +
      "je Kriterium die Zahl der ausgeschlossenen Angebote.",
    props: z.object({
      gesamt: z.number(),
      uebrig: z.number(),
      ausgeschlossen: z.array(z.object({ grund: z.string(), anzahl: z.number() })),
    }),
  },

  GewichtungsPanel: {
    description:
      "Die aus dem Interview abgeleitete Gewichtung, sichtbar und vom Nutzer änderbar.",
    props: z.object({
      gewichte: z.array(z.object({ name: z.string(), anteil: z.number() })),
      hinweis: z.string().optional().default(""),
    }),
  },

  FahrzeugKarte: {
    description:
      "Ein empfohlenes Fahrzeug mit Rang, Eckdaten, Preis und Punktwert. Aufklappbar " +
      "zur vollständigen Begründung: Beitrag je Dimension, begrenzende Bestandteile, " +
      "Gesamtkosten und Vergleich mit dem Zweitplatzierten.",
    props: z.object({
      listingId: z.string(),
      rang: z.number(),
      bezeichnung: z.string(),
      kategorie: z.string(),
      eckdaten: z.string(),
      preis: z.string(),
      haendler: z.string(),
      punkte: z.number(),
      basisAnzahl: z.number(),
      relativHinweis: z.string(),
      dimensionen: z.array(dimension),
      topFaktoren: z.array(z.string()),
      schwachstellen: z.array(z.string()).optional().default([]),
      vergleich: z.string().optional().default(""),
      tcoGesamt: z.number().optional().default(0),
      istMiete: z.boolean().optional().default(false),
    }),
  },
  // ---------------------------------------------------------- progress surface

  PhasenAnzeige: {
    description:
      "Die Phasen eines Zuges als Spur: Interview, Suche, Bewertung, Empfehlung. " +
      "Die aktive Phase ist hervorgehoben.",
    props: z.object({
      phasen: z.array(
        z.object({
          name: z.string(),
          label: z.string(),
          aktiv: z.boolean(),
          erledigt: z.boolean(),
        }),
      ),
    }),
  },

  SlotCheckliste: {
    description:
      "Der Interviewstand als Checkliste. Abgeleitete Werte sind sichtbar von " +
      "gesagten unterschieden und als zu bestätigen markiert.",
    props: z.object({
      zeilen: z.array(
        z.object({
          label: z.string(),
          wert: z.string(),
          herkunft: z.string(),
          offen: z.boolean(),
          zuBestaetigen: z.boolean(),
        }),
      ),
      gefuellt: z.number(),
      gesamt: z.number(),
      hinweis: z.string().optional().default(""),
    }),
  },

  SuchStatus: {
    description:
      "Der Stand der Suche: geprüfte Angebote, verbliebene Angebote und die " +
      "Ausschlusszahlen je Kriterium, sobald sie feststehen.",
    props: z.object({
      aktiv: z.boolean(),
      gesamt: z.number(),
      uebrig: z.number(),
      ausgeschlossen: z.array(z.object({ grund: z.string(), anzahl: z.number() })),
      hinweis: z.string().optional().default(""),
    }),
  },

  WerkzeugStrom: {
    description:
      "Die Werkzeugaufrufe dieses Zuges, während sie geschehen, mit ihrem Status.",
    props: z.object({
      titel: z.string(),
      schritte: z.array(
        z.object({
          werkzeug: z.string(),
          label: z.string(),
          status: z.string(),
        }),
      ),
    }),
  },
} satisfies CatalogDefinitions;
