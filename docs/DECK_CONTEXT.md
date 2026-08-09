# fahrbereit: project context and deck content

Everything needed to write the slide deck, the video script, or to brief someone who
has never seen the project. Every figure here was measured against the repository on
2026-08-09, not estimated. Where a claim is weak, it says so.

**Repository**: `github.com/DevInIndia/fahrbereit`
**Event**: Amulate Summer Hackathon 2026, AI Car Matchmaker
**Author**: Shashank Chauhan

---

## 1. What it is, in one paragraph

fahrbereit is a conversational agent that helps someone in Germany choose a car to
buy or to rent. You describe your situation in your own words. It asks a couple of
follow-up questions, works out what it can from what you said and shows you that
working, then filters a marketplace of 280 listings and explains its ranking with
numbers you can check. It ends with an intake form and a checkout rendered inside the
conversation, and the checkout is a simulation from end to end.

**The interesting part is what the model is not allowed to do.** Filtering, scoring
and cost of ownership are ordinary Python, computed before anything is said. The model
reads those numbers and narrates them. It never produces them, and it is instructed to
say a figure is missing rather than supply a plausible one.

---

## 2. Slide-by-slide content

The template has five slides. This section maps directly onto them.

### Slide 1: Title

```
fahrbereit
An auditable AI car matchmaker for the German market

Amulate Summer Hackathon 2026
Shashank Chauhan
9 August 2026
```

Optional one-line subtitle if there is room:
*The agent explains its reasoning. It does not invent it.*

---

### Slide 2: Solution Overview, three key features

The template wants exactly three. These are the three that matter, strongest first.

**Feature 1: The model never produces a number**

> Filtering, scoring and cost are pure Python, computed before the agent speaks. A
> two-stage engine applies 12 hard constraints, then scores survivors across 6
> weighted dimensions. Every recommendation decomposes into named contributions the
> user can read and check. Same state and dataset always give the same ranking.

**Feature 2: Generative UI over two open protocols**

> The catalogue and the live agent progress are A2UI v0.9 surfaces streamed over SSE,
> not static HTML. The intake form and the simulated checkout are MCP Apps served by
> two separate processes and rendered inside the conversation in sandboxed iframes.

**Feature 3: An interview that shows its working**

> Every answer is stored with its provenance: stated by the user, inferred by the
> agent, or assumed by the system. All three render differently, so a user can see
> what was concluded on their behalf and correct it before it affects the ranking.

If a fourth is ever allowed, use: *8 persona evaluations, 0 hard-constraint
violations, 1.00 of figures traceable to source data.*

---

### Slide 3: Architecture

Use the image. The prompt to generate it is in section 6 of this document.

Speaker notes, four sentences:

> Four containers on one Docker network. The browser talks to nginx, which serves the
> built bundle and proxies the API, so there is one origin and one URL to open. The
> backend holds the agent loop and the deterministic engine, and it holds its own MCP
> client to two separate app servers, so every surface fetch crosses the protocol. The
> orange region is the part with no model in it: filtering, scoring and cost run there
> and finish before the agent is allowed to speak.

---

### Slide 4: Implementation details and stack used

| Layer | Choice | Why |
|---|---|---|
| Agent harness | LangChain **DeepAgents**, `create_deep_agent` | one of the three permitted harnesses |
| Orchestration | **LangGraph** with `InMemorySaver` checkpointer | conversation continuity; required by the AG-UI bridge |
| Model | **Gemini** free tier via a vendor seam | zero cost constraint; no vendor imported outside `agent/model/` |
| Backend | **Python 3.12**, FastAPI, Pydantic | typed models end to end |
| Generative UI | **A2UI v0.9**, `@copilotkit/a2ui-renderer` | catalogue and live progress surfaces |
| Protocol apps | **MCP** `mcp` 2.0 Apps extension | intake form and checkout, two separate servers |
| Streaming | Server-Sent Events | incremental surface updates while the agent works |
| Frontend | **React 19**, Vite 7, vanilla CSS | no CSS framework; design tokens only |
| Typography | **Inter**, bundled offline under SIL OFL | needs a real 300 weight; no CDN dependency |
| Observability | **Langfuse** over **OpenTelemetry** | bonus B-1 |
| Evaluation | 8 personas, judge on Gemma | bonus B-2 |
| Container | **Docker Compose**, four services | `ui`, `backend`, `formular`, `kasse` |
| Method | **spec-kit**, spec-driven | artefacts committed under `specs/` |

**Scale**: 73 commits, ~14,000 lines of Python and TypeScript, 266 automated tests
that need no API key and make no network call.

---

### Slide 5: Conclusion and future evolutions

**What was proven**

- An agent can be genuinely useful while being forbidden from doing arithmetic.
- Protocol-native UI works: A2UI and MCP Apps both render real, interactive surfaces
  inside a conversation.
- Auditability is testable. 266 tests, and 8 persona evaluations with zero
  hard-constraint violations across every persona.

**Known limitations, stated rather than hidden**

- The marketplace is synthetic. Live data was attempted, not skipped: Gemini search
  grounding is the only free path and it returns zero quota on a free-tier key. The
  test, including the control that rules out ordinary rate limiting, is in
  `docs/spike-notes.md` under Spike C.
- Ranking weights are invented and labelled as such in the code. The claim is
  determinism and checkable arithmetic, not that the weights are correct. They are
  user-adjustable, which is the honest answer.
- `RESTWERT_RATE` (residual value) and the 0.39 EUR/kWh household electricity price
  are estimates. Vehicle tax under section 9 KraftStG is exact.
- Session state is in memory. It survives a page reload, not a process restart.

**Next**

- SQLite behind the existing store interface, so state survives a restart.
- Real marketplace data via a paid listings API. `agent/listing.py` is the single
  swap point; everything downstream reads the typed `Listing` model.
- Expand from 8 evaluation personas to 20, and gate merges on the constraint score.

---

## 3. The ten mandatory requirements, and where each lives

| # | Requirement | Where |
|---|---|---|
| M-1 | Multistep agent on a permitted harness | `agent/session.py`, 3 tools in `agent/tools/interview.py` |
| M-2 | Form flow as an MCP App, rendered in chat | `mcpapps/formular/server.py`, `ui://formular/intake.html` |
| M-3 | Mock checkout as an MCP App, rendered in chat | `mcpapps/kasse/server.py`, `ui://kasse/checkout.html` |
| M-4 | Catalogue **and** live progress via A2UI | `agent/surfaces/katalog.py`, `agent/surfaces/fortschritt.py` |
| M-5 | Payment fully mocked and visibly safe | `agent/payment/mock.py`, 24 safety tests |
| M-6 | 100+ listings, 10 categories, 10+ brands each | 280 / 10 / 10 minimum, `data/generate.py` |
| M-7 | State across interview, research, recommendation | `agent/state.py`, `agent/store.py` |
| M-8 | Spec-driven development, artefacts committed | `specs/001-fahrbereit-agent/`, `.specify/` |
| M-9 | Ships as a Docker container | `docker-compose.yml`, four services |
| M-10 | Public repo with a README that runs | `README.md` |
| B-1 | Observability | `agent/observability.py` |
| B-2 | Evaluations | `evals/` |

The brief also names four things the interview must capture: **what they want to do,
the type of car, budget, and target date.** All four are captured. The target date is
also enforced as a hard availability constraint on rentals.

---

## 4. Verified numbers

Measured on 2026-08-09. Safe to put on a slide.

| Metric | Value |
|---|---|
| Listings | **280** |
| Categories | **10** |
| Minimum brands per category | **10** |
| Rental listings | 55 |
| Hard constraints | **12**, applied in fixed order |
| Scoring dimensions | **6**, weighted, percentile-normalised |
| Tools exposed to the model | **3** |
| Automated tests | **266**, no API key, no network |
| Persona evaluations | **8**, two of them rentals |
| Hard-constraint violations across all personas | **0** |
| Figures traceable to source data | **1.00** |
| Slot-filling completeness | 0.93 |
| Judged faithfulness | 0.94 |
| Model calls for a full eval run | 68 |
| Commits | 73 |

**On the 0.94 judged faithfulness**: one persona scored 0.50 because the agent
described a purchase price as a five-year cost. The figure was genuine, so the
deterministic number check passed it; only the label was wrong. That result is kept in
the published table rather than tuned away, because it is the clearest evidence that
the deterministic layer and the judge measure different things.

---

## 5. How the ranking works, for the worked example

Two stages, both pure Python, both before the model speaks.

**Stage 1, hard filter.** 12 constraints applied in a fixed order: listing type,
category, budget, transmission, fuel, seats, boot volume, emissions badge, mileage,
accident history, availability, distance. Each excluded listing is attributed to the
first constraint it fails, so the drop counts sum exactly to the number excluded and
the report can be read aloud without double counting.

**Stage 2, weighted score.** Survivors are scored across 6 dimensions: price headroom,
total cost, age and mileage, fitness for purpose, condition, distance. Each dimension
is percentile-normalised against the surviving pool, so no dimension can silently
flatten into a constant. Weights are derived from the interview and are user
adjustable.

**Worked example, the rental persona** (`python -m scripts.demo_ranking --persona umzug`):

```
280 listings checked
  minus 225  listing type      (not a rental)
  minus  19  budget            (over 95 EUR/day)
  minus  12  boot volume       (under 350 l)
  minus  21  distance          (over the assumed 100 km pickup radius)
      3 remaining
```

Cost models are separate and each refuses the other's input. A purchase gets five-year
ownership cost including exact section 9 KraftStG vehicle tax. A rental gets base rate
over days held, fuel over the expected distance, and excess kilometres above the
offer's own allowance, with the deposit reported alongside the total rather than
inside it, because refundable money is not a cost.

---

## 6. Prompt for the architecture image

Paste this into an image or diagram generator. It describes the real system.

```
A clean technical architecture diagram, flat vector, landscape 16:9.

Style: minimalist Swiss technical drawing. Dark charcoal background (#111318).
Off-white text (#F1F2F4). Thin 1px borders on every box. One accent colour, a
burnt orange (#D8531F), used only for the highlighted region and its label.
Generous whitespace. No gradients, no drop shadows, no 3D, no glossy effects,
no clip art, no photographs. Monospace or neo-grotesque sans labels only.

Layout, five horizontal bands top to bottom, connected by thin vertical arrows:

BAND 1, "BROWSER": one wide box containing four small boxes in a row, labelled
"React 19 + Vite", "A2UI renderer", "MCP app bridge", "SSE reader".

BAND 2, "CONTAINER 1: ui": one wide thin box labelled
"nginx, serves the built bundle, proxies /api". Port tag ":8080" on the right.

BAND 3, the largest: on the LEFT a tall box labelled "CONTAINER 2: backend"
with port tag ":8000", containing two rows.
  Row A, two boxes side by side: "Agent loop, DeepAgents + LangGraph
  checkpointer" and "3 tools the model may call".
  Row B, a WIDE REGION OUTLINED AND LABELLED IN THE ORANGE ACCENT, titled
  "DETERMINISTIC CORE, NO MODEL IN THE PATH", containing four small boxes:
  "typed state with provenance", "hard filter, 12 constraints", "weighted
  score, 6 dimensions", "cost models, ownership and rental".
On the RIGHT, beside the backend box, two small stacked boxes labelled
"CONTAINER 3: formular, MCP App :3001" and "CONTAINER 4: kasse, MCP App
:3002", joined to the backend by a horizontal arrow labelled "MCP over HTTP".

BAND 4: two small boxes, "Langfuse over OpenTelemetry" and "280 synthetic
listings, seeded generator".

BAND 5, a full width strip in the orange accent, containing one line of larger
text: "The model reads these numbers and narrates them. It never produces them."

Every label must be short and legible. Do not invent components that are not
listed here.
```

**Then verify what comes back.** Generators routinely add plausible boxes that do not
exist. Check that it shows exactly four containers, that ports read 8080, 8000, 3001,
3002, that the highlighted region is the deterministic core, and that nothing named
"database", "cache", "load balancer", "vector store" or "Kubernetes" has appeared.
None of those are in this system.

---

## 7. Prompt for the tech stack image (slide 4)

```
A flat vector technology stack diagram, landscape 16:9, dark charcoal
background (#111318), off-white text (#F1F2F4), one burnt orange accent
(#D8531F) used only for section headers. Thin 1px borders, generous
whitespace, no gradients or shadows.

Five labelled horizontal layers, stacked, each a thin wide box containing
short pill-shaped tags:

  FRONTEND        React 19 · Vite 7 · TypeScript · vanilla CSS · Inter
  PROTOCOLS       A2UI v0.9 · Model Context Protocol · Server-Sent Events
  AGENT           LangChain DeepAgents · LangGraph · Gemini via a vendor seam
  DETERMINISTIC   Python 3.12 · FastAPI · Pydantic · pure-Python ranking and
                  cost engine
  PLATFORM        Docker Compose, 4 services · Langfuse · OpenTelemetry ·
                  266 tests

Put the DETERMINISTIC layer in the orange accent to mark it as the core.
Text only, no vendor logos.
```

---

## 8. Things to say out loud in the video

- The marketplace is synthetic: 280 generated listings, not live inventory.
- Payment is fully simulated. No card input field exists anywhere in the codebase,
  and a test walks the source tree to keep it that way.
- Every number on screen was computed in Python before the model spoke.
- The three footer presets call no model at all, which is why they still work when the
  daily quota is gone.

---

## 9. One-line elevator pitches

**Technical**: A multistep agent whose recommendations are computed by a deterministic
Python engine and only narrated by the model, with generative UI over A2UI and MCP.

**Plain**: It helps you pick a car, and it shows you the arithmetic.

**The differentiator**: Most agent demos ask you to trust the model. This one is built
so you do not have to.
