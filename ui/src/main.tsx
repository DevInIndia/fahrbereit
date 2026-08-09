import React from "react";
import { createRoot } from "react-dom/client";

/**
 * Three weights, self hosted, imported before the stylesheet so the cascade has
 * them when it first paints.
 *
 * Self hosted rather than pulled from a font CDN on purpose. A CDN is a network
 * dependency at page load: it fails offline, it fails behind a restrictive network,
 * and it fails in front of an audience. Vite fingerprints these into the bundle, so
 * the container serves them from the same origin as everything else.
 *
 * Only 300, 400 and 600 are imported, because those are the only three the design
 * uses, and only the latin subset of each. The unsuffixed imports pull every subset
 * the family ships, Cyrillic and Greek and Vietnamese included, which is 21 files
 * and 1.2 MB in the image to render an interface that exists in German and English.
 * A browser would only ever fetch the latin ones; the rest are pure weight.
 */
import "@fontsource/inter/latin-300.css";
import "@fontsource/inter/latin-400.css";
import "@fontsource/inter/latin-600.css";

import "@fontsource/outfit/latin-300.css";
import "@fontsource/outfit/latin-400.css";
import "@fontsource/outfit/latin-600.css";

import App from "./App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
