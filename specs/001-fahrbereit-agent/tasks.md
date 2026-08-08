---

description: "Task breakdown for fahrbereit, organised as walking skeleton milestones"
---

# Tasks: fahrbereit, a conversational car buying and rental advisor

**Input**: Design documents from `/specs/001-fahrbereit-agent/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md

**Organisation**: milestones, not layers. Milestone 1 is a complete but shallow journey
from first message to simulated checkout. Later milestones replace shallow pieces with
real ones, one at a time, and the system stays runnable after every change.

**Standing rule**: the tree must never be left in a state where `docker compose up`
fails.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel, touches different files with no dependency
- **[Story]**: the user story from spec.md this task serves

---

## Phase 0: De-risking (gates M-1, M-2, M-3, M-4)

**Blocked**: requires a Google AI Studio API key in the build environment.

- [ ] T000 Spike 0. Verify the model path before anything is built on it: one minimal
  call through `ChatGoogleGenerativeAI`, then one multi tool calling exchange, then one
  `create_deep_agent` run that calls a trivial tool and returns. Record observed latency
  and any throttling. This gates T001 and T002, which both need a working agent.
- [ ] T001 Spike A. Does the MCP Apps middleware render an app surface in chat behind an
  external Python AG-UI endpoint? One MCP server, one tool carrying
  `_meta.ui.resourceUri`, one single file hello world surface, one DeepAgents session
  behind `add_langgraph_fastapi_endpoint`, one Node process running the middleware, one
  React page. Success requires both a render and a button click round trip. Scratch tree
  only.
- [ ] T002 Spike B. Render a car card with image, specification table and action from an
  agent emitted message, using `ag_ui_langgraph.get_a2ui_tools` against a catalog built
  with `createCatalog`, and confirm the surface update, component update, data model
  update and begin rendering flow. Scratch tree only.
- [ ] T003 Record all outcomes in `docs/spike-notes.md` with exact error text on any
  failure, state which architecture path is selected, then discard the spike code.

**Spike A path**: under this stack the Node process hosting the middleware in front of the
Python endpoint is the documented topology, not a fallback. The remaining fallback is
hosting the app bridge directly in React and rendering the iframe ourselves. The path is
reported before anything is built on it.

---

## Milestone 1: Walking skeleton (target hour 12)

**Definition of done**: a user completes the entire journey, interview to simulated
checkout, from a clean clone via `docker compose up`. Shallow and plain by design.

### Setup

- [x] T004 Scaffold the spec-kit workflow and add `.gitignore`.
- [ ] T005 Create the source tree from plan.md.
- [ ] T006 [P] Add `pyproject.toml` pinning the Python dependencies from plan.md,
  including `fastapi` and `uvicorn`, which `ag-ui-langgraph` needs but does not declare.
- [ ] T007 [P] Add `.env.example` with placeholder values for `MODEL_PROVIDER`,
  `GOOGLE_API_KEY`, `PAYMENT_PROVIDER` and the Langfuse variables. No Anthropic key is
  required by this project.
- [ ] T007a Implement the model provider seam in `agent/model/`: `factory.py` reading
  `MODEL_PROVIDER` and returning a `BaseChatModel`, `gemini.py`, and
  `openai_compatible.py` covering Cerebras and Groq through a `base_url` override.
  Nothing outside this package imports a vendor.
- [ ] T007b [P] Test the seam in `tests/test_model_factory.py`: the factory returns the
  right class per configuration value, raises legibly on an unknown value, and no module
  outside `agent/model/` imports a vendor package. The last assertion is a grep over the
  tree and is what actually keeps the seam honest.

### Shallow data

- [ ] T008 Hand write twenty listings in `data/listings.json` against the final schema
  from data-model.md, covering both purchase and rental. No generator yet.
- [ ] T009 Implement listing loading and search in `agent/tools/search.py`.

### Shallow core (M-7 in memory)

- [ ] T010 Implement the typed state in `agent/state.py` with three slots only: intent,
  budget, category. Provenance wrapper included from the start so it does not need
  retrofitting.
- [ ] T011 Implement session state in memory keyed by session id in `agent/store.py`,
  behind an interface that a persistent implementation can satisfy later.
- [ ] T012 Implement hard filter only in `agent/tools/ranking.py`, ordered by price.

### Shallow agent (M-1)

- [ ] T013 Write a minimal system prompt and interview policy in `agent/prompts/`.
- [ ] T014 Orchestrate the session in `agent/session.py` with `create_deep_agent`, passing
  the model from the factory, the tools, and a LangGraph checkpointer.
- [ ] T015 Expose the agent over AG-UI in `agent/server.py` using
  `add_langgraph_fastapi_endpoint`.
- [ ] T015a Handle provider rate limiting as a visible state rather than a failure, per
  FR-044.

### Shallow interface (M-4, one surface)

- [ ] T016 Scaffold the React client in `ui/` with the transport client and a session id.
- [ ] T017 Define a minimal component catalog in `ui/src/a2ui/` and a plain car card list
  surface, emitted from the agent side via `ag_ui_langgraph.get_a2ui_tools`.
- [ ] T017a Stand up the Node process running `MCPAppsMiddleware` in front of the Python
  AG-UI endpoint, as a compose service. This is the documented topology, so it is part of
  the architecture rather than a contingency.

### Shallow MCP Apps (M-2, M-3)

- [ ] T018 Build `mcp/formular/` with a tool carrying `_meta.ui.resourceUri` and a three
  field surface, no validation, bundled to a single HTML file.
- [ ] T019 Build `mcp/kasse/` with a surface showing a total and a persistent SIMULATION
  banner, no tax breakdown yet.
- [ ] T020 Define the `PaymentProvider` interface and `MockPaymentProvider` in
  `agent/payment/`, resolved through a factory keyed by `PAYMENT_PROVIDER`. See Milestone
  1 payment note below.
- [ ] T021 Attach the MCP Apps middleware and confirm both surfaces render in chat.

### Containers (M-9), not deferred

- [ ] T022 Write the `Dockerfile` set and `docker-compose.yml` for agent, MCP servers and
  client.
- [ ] T023 Verify `docker compose up` from a clean clone with only an API key present.
  **Milestone 1 does not complete until this passes.**

### Documentation (M-10)

- [ ] T024 First `README.md` pass covering sections 1, 3, 4, 7, 9 and 10.

**Payment note for T020**: the provider seam is built at Milestone 1 rather than
retrofitted at Milestone 3, because the interface shape determines what the checkout
surface and the agent may know about payment. Retrofitting it later would mean touching
the surface, the agent and the tests at once.

---

## Milestone 2: Substance (target hour 26)

Each task replaces one shallow piece with the real one, keeping the system working.

### Real marketplace (M-6)

- [ ] T025 Write the German vocabulary tables in `data/vocab.py`: ten categories, at least
  ten brands with model lines and trims per category, invented dealer and operator name
  parts, postal codes with places.
- [ ] T026 Implement the seeded generator in `data/generate.py` producing correlated
  purchase listings.
- [ ] T027 Extend the generator with rental listings carrying ACRISS codes, rates, minimum
  period, included and excess kilometres, deposit, minimum age and availability window.
- [ ] T028 Regenerate and commit `data/listings.json` with at least two hundred and fifty
  listings, exactly ten categories, at least ten brands in each.
- [ ] T029 [P] Write invariant tests in `tests/test_dataset.py`. Includes a coherence test
  that fails when an older, higher mileage car in the same category and trim is priced
  above a newer, lower mileage one. Also scale floors, both listing types per category,
  badge follows emissions class, no reserved real world operator name, and byte for byte
  regeneration from the seed.

### Real interview (US1)

- [ ] T030 Extend `agent/state.py` to the full slot set from data-model.md.
- [ ] T031 Implement inference with explicit confirmation, the at most two questions rule,
  and the never re-ask rule in `agent/prompts/`.
- [ ] T032 [P] Test slot extraction and the no re-ask rule in `tests/test_interview.py`.

### Real ranking (US2)

- [ ] T033 Add per constraint drop count attribution to the hard filter in a fixed order.
- [ ] T034 Implement weighted soft scoring over the six dimensions with weights derived
  from interview state.
- [ ] T035 Expose weights to the user and re-rank in place on adjustment.
- [ ] T036 [P] Test ranking in `tests/test_ranking.py`: determinism, zero hard constraint
  violations, contributions summing to the total, drop counts summing to the excluded
  count, and the empty result path.

### Real state (M-7)

- [ ] T037 Replace the in memory store with SQLite persistence in `agent/store.py`, and
  attach a persistent LangGraph checkpointer for conversation continuity. These are two
  separate concerns sharing one database, per plan.md.
- [ ] T038 Verify state survives a page refresh and a backend restart.
- [ ] T039 Implement the invalidation map from data-model.md, so a budget change discards
  the ranking and keeps the interview.
- [ ] T040 [P] Test invalidation in `tests/test_state.py`.

### Second dynamic surface (M-4)

- [ ] T041 Build the live progress surface: slot checklist with inferred values visually
  distinct from stated ones, current phase, search status with filter counts, streaming
  tool calls.
- [ ] T042 Verify both surfaces update incrementally rather than by replacement.

- [ ] T043 README pass two.

---

## Milestone 3: Depth (target hour 36)

- [ ] T044 **Before writing any TCO code**: add to `research.md` the exact Kfz-Steuer
  formula to be implemented, with its source, stating the per 100 cubic centimetre rate
  for petrol and for diesel, the carbon dioxide allowance and the per gram rates by band,
  the registration era boundaries that select between flat and banded rates, and the
  electric vehicle exemption cutoff being assumed. The assumption is stated on the page,
  not buried in a function.
- [ ] T045 Implement German cost of ownership in `agent/tools/tco.py`: motor vehicle tax,
  insurance band, energy cost at the user's annual mileage, maintenance by segment and
  age, five year residual value.
- [ ] T046 [P] Test in `tests/test_tco.py`: the tax formula against hand computed cases
  per fuel type and registration era, and the identity that itemised terms sum to the
  total.
- [ ] T047 Build the "Warum dieses Auto" panel from score data only: per dimension bars,
  dominant factors, quantified runner up comparison.
- [ ] T048 Extend `kasse` to a full invoice: net, nineteen percent value added tax and
  gross as separate lines.
- [ ] T049 Add purchase and rental contract references, the mock payment reference and the
  obviously invalid bank identifier, each carrying the SIMULATION token, plus the
  confirmation watermark.
- [ ] T050 [P] Test the checkout surface in `tests/test_kasse.py`: indicators present, tax
  line separated, and no card input present anywhere in any state.
- [ ] T051 Design pass across all surfaces: tabular figures, strict grid, hairline rules,
  restrained instrument panel aesthetic.
- [ ] T052 Build `mcp/markt/` exposing `search_listings`, `get_listing` and
  `check_availability` over MCP. **First item in the cut order.**
- [ ] T053 README pass three, including the worked ranking example with real numbers.

---

## Milestone 4: Bonus (target hour 41, cut first if behind)

- [ ] T054 Wire OpenTelemetry and Langfuse in `agent/observability.py` using
  `openinference-instrumentation-langchain`, instrumented at startup, with ranking tool
  inputs and outputs attached to spans. Requires Langfuse keys, which must be requested.
- [ ] T055 Write eight personas in `evals/personas.json`, each with a hidden ground truth
  need.
- [ ] T056 Build the harness in `evals/run_evals.py` scoring slot filling completeness,
  hard constraint violations deterministically, rationale faithfulness by model judgement,
  and turns to complete state.
- [ ] T057 Expand to twenty personas only if time allows.
- [ ] T058 Run the suite and commit results to `evals/results/`.

---

## Milestone 5: Deliverables (hours 41 to 46)

- [ ] T059 README final pass, all eleven sections, including the requirements
  traceability table and honest known limitations.
- [ ] T060 [P] Write `docs/architecture.md`.
- [ ] T061 Capture the four required screenshots.
- [ ] T062 Slide deck against the organisers' template.
- [ ] T063 Script and record the demonstration video.
- [ ] T064 Walk the M-1 to M-10 table and name the file satisfying each row.

---

## Cut order if behind schedule

1. `markt` MCP server (T052)
2. Eval persona count (T057, then T055 to T058 entirely)
3. TCO sophistication (T045 reduces to tax and energy only)
4. Design polish (T051)

Never cut: the two MCP Apps, the dynamic surfaces, Docker, or the README.

## Dependencies

- Phase 0 gates T017 to T021 and T041. Everything else may proceed regardless.
- T023 gates the whole of Milestone 2. Containers are proven at hour 12, not at hour 45.
- T044 gates T045. The formula is written down and sourced before it is coded.
- Milestone 2 gates Milestone 3. Milestone 3 gates Milestone 4.
- Milestone 4 is cut in full before any Milestone 1 to 3 item is compromised.
