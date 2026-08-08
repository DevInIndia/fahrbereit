"""One stylesheet, shared by every MCP App surface.

Braun and Swiss instrument panel: graphite ground, one accent, hairline rules, a
strict grid, generous whitespace. Every numeral uses tabular figures so columns
align, which is the whole reason the tables are readable at a glance.

No gradients, no glassmorphism, no glow, no drop shadows on cards, no rounded
everything. Motion only where it carries a state change.
"""

CSS = """
:root {
  --ground:   #131313;
  --panel:    #1a1a1a;
  --rule:     #2e2e2e;
  --ink:      #ececec;
  --ink-dim:  #8d8d8d;
  --ink-faint:#5f5f5f;
  --accent:   #d8531f;
  --warn:     #e0a02a;
  --ok:       #4d9d6b;
}

* { box-sizing: border-box; }

html, body {
  margin: 0;
  padding: 0;
  background: var(--ground);
  color: var(--ink);
  font: 400 14px/1.5 "Inter", "Helvetica Neue", Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
}

body { padding: 20px 22px 24px; }

/* Every numeral aligns. This is not decoration, it is what makes the tables read. */
.num, td.num, input, output, table {
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum" 1;
}

h1, h2, h3 { font-weight: 500; letter-spacing: -0.01em; margin: 0; }
h1 { font-size: 17px; }
h2 { font-size: 14px; margin-bottom: 12px; }

.eyebrow {
  font-size: 10px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-faint);
  margin-bottom: 6px;
}

hr { border: 0; border-top: 1px solid var(--rule); margin: 18px 0; }

.grid { display: grid; grid-template-columns: repeat(12, 1fr); gap: 14px; }
.col-6  { grid-column: span 6; }
.col-12 { grid-column: span 12; }
@media (max-width: 520px) { .col-6 { grid-column: span 12; } }

label {
  display: block;
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--ink-dim);
  margin-bottom: 5px;
}

input, select {
  width: 100%;
  background: var(--panel);
  border: 1px solid var(--rule);
  border-radius: 0;
  color: var(--ink);
  padding: 9px 10px;
  font-size: 14px;
  font-family: inherit;
}
input:focus, select:focus { outline: none; border-color: var(--accent); }
input[aria-invalid="true"] { border-color: var(--accent); }

.error { color: var(--accent); font-size: 11px; margin-top: 4px; min-height: 13px; }

button {
  background: var(--accent);
  color: #fff;
  border: 0;
  border-radius: 0;
  padding: 11px 22px;
  font: 500 13px/1 inherit;
  letter-spacing: 0.03em;
  cursor: pointer;
}
button:disabled { background: var(--rule); color: var(--ink-faint); cursor: not-allowed; }
button.secondary { background: transparent; border: 1px solid var(--rule); color: var(--ink-dim); }

table { width: 100%; border-collapse: collapse; }
td, th { padding: 7px 0; text-align: left; font-weight: 400; }
th { color: var(--ink-faint); font-size: 10px; letter-spacing: 0.12em; text-transform: uppercase; }
td.num, th.num { text-align: right; }
tr + tr td { border-top: 1px solid var(--rule); }
tr.total td { border-top: 1px solid var(--ink-faint); font-weight: 500; padding-top: 10px; }
.dim { color: var(--ink-dim); }

/* The simulation notice. Present on every screen, unmissable, never dismissible. */
.sim-banner {
  background: repeating-linear-gradient(
    45deg, #2a1a0d, #2a1a0d 9px, #241608 9px, #241608 18px
  );
  border: 1px solid var(--warn);
  color: var(--warn);
  padding: 9px 12px;
  font-size: 11px;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  margin-bottom: 16px;
}
.sim-banner strong { color: #ffd479; letter-spacing: 0.16em; }

.watermark {
  position: relative;
  overflow: hidden;
}
.watermark::after {
  content: "SIMULATION";
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%) rotate(-24deg);
  font-size: 58px;
  font-weight: 700;
  letter-spacing: 0.18em;
  color: rgba(224, 160, 42, 0.13);
  pointer-events: none;
  white-space: nowrap;
}

.ref {
  font-family: "SF Mono", "Consolas", monospace;
  font-size: 12px;
  color: var(--warn);
  word-break: break-all;
}

.footnote { color: var(--ink-faint); font-size: 11px; margin-top: 14px; }
.status { font-size: 12px; color: var(--ink-dim); margin-top: 12px; min-height: 16px; }
.status.ok { color: var(--ok); }
.status.err { color: var(--accent); }
"""
