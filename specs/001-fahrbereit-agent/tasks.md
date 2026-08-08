---

description: "Task breakdown for fahrbereit, reconciled against what was actually built"
---

# Tasks: fahrbereit, a conversational car buying and rental advisor

**Input**: Design documents from `/specs/001-fahrbereit-agent/`

**Reconciled**: 2026-08-08, against the tree at commit `f741903`. Ticks below mean the
work exists, runs, and is covered by a test or was verified by running it. Where a task
was cut or changed, it says so and why, rather than being deleted.

**Handover for a fresh session**: `docs/state.md`.

---

## Phase 0: De-risking

- [x] T000 Spike 0, the model path. **Pass.** Tool calling reliable on both Lite
  variants. Found that Gemma is sixteen times slower and cannot disable its thinking
  blocks, which moved it off every interactive path.
- [x] T001 Spike A, MCP Apps behind an external Python endpoint. **Partial, unresolved.**
  The protocol layer is proven end to end; `@ag-ui/mcp-apps-middleware` 0.0.3 injected
  zero tools and the cause was never established. Recorded honestly rather than deleted.
- [~] T002 Spike B, A2UI from an agent emitted message. **Folded into the real build.**
  Proving it twice was not worth a separate run; it is proven by the catalogue surface.
- [x] T003 Outcomes recorded in `docs/spike-notes.md`, with exact error text. Path 2
  selected: we host the app bridge ourselves.

---

## Milestone 1: Walking skeleton

- [x] T004 Spec-kit workflow scaffolded, `.gitignore` added.
- [x] T005 Source tree created.
- [x] T006 `pyproject.toml`. Later fixed: it had no `[build-system]` and pinned
  `langchain-core` exactly, so `pip install -e .` was impossible.
- [x] T007 `.env.example` with placeholder values only.
- [x] T007a Model provider seam in `agent/model/`, factory reading `MODEL_PROVIDER`.
- [x] T007b Seam enforced by a test that walks the tree for vendor imports.
- [x] T008 Hand written listings, since replaced by the generator.
- [x] T009 Listing loading in `agent/listing.py`.
- [x] T010 Typed state with provenance in `agent/state.py`, full slot set from the start.
- [x] T011 Session store in `agent/store.py`, in memory behind a swappable interface.
- [x] T012 Hard filter in `agent/tools/ranking.py`.
- [x] T013 System prompt and interview policy in `agent/prompts/system.py`.
- [x] T014 Session orchestration in `agent/session.py`, `checkpointer=InMemorySaver()`
  wired at construction.
- [x] T015 HTTP surface in `agent/server.py`.
- [x] T015a Rate limiting surfaced as a visible state, FR-044.
- [x] T016 React client in `ui/`.
- [x] T017 A2UI component catalog and the catalogue surface.
- [~] T017a Node process running `MCPAppsMiddleware`. **Cut.** Superseded by the Path 2
  decision; the bridge is hosted in React and the backend holds its own MCP client.
- [x] T018 `mcpapps/formular/`, MCP App with `_meta.ui.resourceUri`.
- [x] T019 `mcpapps/kasse/`, MCP App with the SIMULATION banner.
- [x] T020 `PaymentProvider` interface and `MockPaymentProvider`, resolved by factory.
- [x] T021 Both surfaces render in chat, verified in a browser.
- [x] T022 `Dockerfile` and `docker-compose.yml`, four services.
- [x] T023 `docker compose up` verified from a clean clone in a temp directory.
- [x] T024 First README pass.

---

## Milestone 2: Substance

- [x] T025 German vocabulary tables in `data/vocab.py`.
- [x] T026 Seeded generator in `data/generate.py`.
- [x] T027 Rental listings with ACRISS codes, rates, deposit, availability.
- [x] T028 280 listings committed, ten categories, at least ten brands in each.
- [x] T029 Invariant tests including the price coherence guarantee.
- [x] T030 Full slot set.
- [x] T031 Inference with explicit confirmation, at most two questions, never re-ask.
- [x] T032 Interview behaviour tests in `tests/test_agent_loop.py`.
- [x] T033 Per constraint drop counts in a fixed order.
- [x] T034 Weighted soft scoring over six dimensions.
- [x] T035 Weights exposed and adjustable, re-ranking in place.
- [x] T036 Ranking tests: determinism, zero constraint violations, arithmetic identities.
- [ ] T037 **Not done.** SQLite persistence. Still in memory. M-7 as stated requires a
  page reload, which is met; a process restart is not. The interface is ready for the swap.
- [x] T038 State survives a page reload.
- [x] T039 Invalidation map implemented.
- [x] T040 Invalidation tested: a budget change discards the ranking and keeps the
  interview; a weight change never re-runs the filter.
- [x] T041 Live progress surface in `agent/surfaces/fortschritt.py`, streamed over SSE.
- [x] T042 Incremental updates verified: each event carries only the changed component.
- [x] T043 README pass two.

---

## Milestone 3: Depth

- [x] T044 Kfz-Steuer formula written into `specs/001-fahrbereit-agent/research.md` with its source before any code,
  including the extended electric exemption to 31.12.2030. The widely quoted 2025 date is
  stale.
- [x] T045 German five year cost of ownership in `agent/tools/tco.py`.
- [x] T046 Tax tested against hand computed cases per fuel type and registration era.
- [x] T047 "Warum dieses Auto" panel, built from score data only.
- [x] T048 Full invoice: net, nineteen percent tax, gross as separate lines.
- [x] T049 Contract and payment references, invalid IBAN, watermark, all carrying the
  SIMULATION token.
- [x] T050 Checkout tested: indicators present, tax separated, no card input anywhere in
  the repository in any state.
- [x] T051 Design pass: tabular figures, strict grid, hairline rules.
- [~] T052 `markt` MCP server. **Cut, as planned.** First in the cut order. The brief
  explicitly permits calling marketplace data directly, which is what the agent does.
- [ ] T053 README pass three with the worked ranking example. **Outstanding.**

---

## Milestone 4: Bonus

- [x] T054 Langfuse over OpenTelemetry in `agent/observability.py`. Verified by reading a
  trace back from the API: 20 observations per turn. `fahrbereit.ranking` carries the
  filter counts, weights and per dimension contributions, satisfying FR-035.
- [x] T055 Eight personas in `evals/personas.json`.
- [x] T056 Harness in `evals/run_evals.py`.
- [ ] T057 Expand to twenty personas. Only if time allows.
- [x] T058 Run the suite, commit results in `evals/results.json`.

---

## Milestone 5: Deliverables

- [x] T059 README final pass: disclosures, worked example, traceability table, honest
  known limitations naming `RESTWERT_RATE` and household electricity price.
- [ ] T060 `docs/architecture.md`.
- [ ] T061 Four screenshots.
- [ ] T062 Slide deck. **Required for submission.**
- [ ] T063 Video demo. **Required for submission.**
- [x] T064 Requirement traceability walked. All ten mandatory requirements map to a file;
  table added to README.

---

## Queued bugs (ALL FIXED)

- [x] B-1 Rental flow applies the five year **ownership** cost model to rentals. Fixed in `8f78435`. Replaced with rental cost model and labelled Mietkosten.
- [x] B-2 Pickup distance is a soft weight for rentals. Fixed in `cb3e824`. Added 100 km default pickup radius for rentals. *Note: Task description overstated work; hard constraint already existed in CONSTRAINT_ORDER, _fails, drop counts, and i18n, missing only a rental default.*
- [x] B-3 Residual raw display strings. Fixed in `e8675da`. `"Škoda"` corrected in `data/vocab.py` and regenerated. Added tree-walking display string test.

---

## Cut, deliberately

1. `markt` as an MCP App (T052). Optional in the brief; first in the agreed cut order.
2. The AG-UI MCP Apps middleware topology (T017a). Superseded by Path 2.
3. Spike B as a separate exercise (T002). Proven inside the real deliverable instead.
4. Twenty evaluation personas (T057). Eight is the target if the harness is built at all.

## Dependencies still live

- T055 to T058 gate the eval results table in T059.
- T045's rental branch is what B-1 fixes; do B-1 before quoting rental costs anywhere.
- Nothing gates the deck or the video except the screenshots in T061.
