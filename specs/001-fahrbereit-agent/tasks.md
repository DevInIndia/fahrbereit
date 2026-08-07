---

description: "Task breakdown for fahrbereit"
---

# Tasks: fahrbereit, a conversational car buying and rental advisor

**Input**: Design documents from `/specs/001-fahrbereit-agent/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md

**Tests**: included. The specification asserts determinism, arithmetic identities and
dataset invariants as measurable outcomes, so those tests are part of the deliverable
rather than optional.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel, touches different files with no dependency
- **[Story]**: the user story from spec.md this task serves

---

## Phase 0: De-risking

**Purpose**: prove the two unverified integration paths before any surface is designed.
Blocked on API key access.

- [ ] T001 Spike the MCP App render path behind an external agent endpoint, per
  research.md spike 1. Scratch tree only.
- [ ] T002 Spike a non-trivial dynamic component rendered from an agent emitted message,
  per research.md spike 2. Scratch tree only.
- [ ] T003 Record both outcomes and the resulting architecture decision in
  `docs/spike-notes.md`, then discard the spike code.

---

## Phase 1: Setup

- [x] T004 Scaffold the spec-kit workflow and add `.gitignore`.
- [ ] T005 Create the source tree from plan.md: `agent/`, `mcp/`, `ui/`, `data/`,
  `evals/`, `tests/`, `docs/`.
- [ ] T006 [P] Add `pyproject.toml` pinning the Python dependencies from plan.md.
- [ ] T007 [P] Add `.env.example` documenting `ANTHROPIC_API_KEY` and the Langfuse
  variables with placeholder values only.

---

## Phase 2: Marketplace data

**Purpose**: inventory, which everything downstream reads. No dependency on a model.

- [ ] T008 Write the German vocabulary tables in `data/vocab.py`: ten categories, at least
  ten brands with model lines and trims per category, invented dealer and operator name
  parts, postal codes with places.
- [ ] T009 Implement the seeded generator in `data/generate.py` producing correlated
  purchase listings: registration, mileage, power, displacement, mass, consumption,
  emissions, emissions class, environmental badge, inspection date, owners, price.
- [ ] T010 Extend the generator with rental listings carrying ACRISS codes, rates, minimum
  period, included and excess kilometres, deposit, minimum age and availability window.
- [ ] T011 Generate and commit `data/listings.json`.
- [ ] T012 [P] Write dataset invariant tests in `tests/test_dataset.py`: scale floors,
  brands per category, both listing types per category, price monotonicity within a model
  line, badge follows emissions class, no reserved real world operator name, byte for byte
  regeneration from the seed. Satisfies SC-009 and SC-010.

---

## Phase 3: Deterministic core (US2)

**Purpose**: the ranking differentiator. Testable without a model, an interface or a key.

- [ ] T013 Implement the typed state in `agent/state.py`: slot wrapper with provenance,
  the slot set, budget and hard constraint structures, the phase enum.
- [ ] T014 Implement the invalidation map from data-model.md in `agent/state.py` and prove
  it in `tests/test_state.py`: a weight change preserves the filter, a budget change
  preserves the interview. Satisfies US6.
- [ ] T015 Implement SQLite session persistence in `agent/store.py` with atomic writes.
- [ ] T016 [P] Test persistence across a simulated process restart in
  `tests/test_store.py`. Satisfies SC-008 and US7.
- [ ] T017 Implement German cost of ownership in `agent/tools/tco.py`: motor vehicle tax
  for combustion and electric, insurance band, energy, maintenance, residual value.
- [ ] T018 [P] Test cost of ownership in `tests/test_tco.py`: the tax formula against hand
  computed cases per fuel type and registration era, and the identity that itemised terms
  sum to the reported total.
- [ ] T019 Implement the hard filter in `agent/tools/ranking.py` with per constraint
  elimination attribution in a fixed order.
- [ ] T020 Implement weighted scoring in `agent/tools/ranking.py` over the six dimensions,
  with weight derivation from interview state.
- [ ] T021 Implement the runner up comparison producing quantified deltas only.
- [ ] T022 [P] Test ranking in `tests/test_ranking.py`: determinism across repeated runs,
  zero hard constraint violations in output, contributions summing to the total,
  elimination counts summing to the excluded count, and the empty result path.
  Satisfies SC-001, SC-004 and SC-005.
- [ ] T023 Implement marketplace query functions in `agent/tools/search.py`: search,
  single retrieval, availability against a target date.

---

## Phase 4: Agent session (US1)

- [ ] T024 Write the system prompt and interview policy in `agent/prompts/`: infer before
  asking, confirm inferences, at most two questions per turn, never re-ask a filled slot,
  narrate scores rather than produce them.
- [ ] T025 Register the tools in process and orchestrate the session in
  `agent/session.py` with the phase machine and persistence wiring.
- [ ] T026 Verify a full interview to recommendation conversation from a terminal client.
- [ ] T027 [P] Test slot extraction and the no re-ask rule in `tests/test_interview.py`.

---

## Phase 5: Marketplace MCP server

- [ ] T028 Implement `mcp/markt/` exposing `search_listings`, `get_listing` and
  `check_availability` over MCP, wrapping `agent/tools/search.py`.
- [ ] T029 Wire the server into the session config with the tools pre-approved so no
  permission prompt can interrupt a demonstration.

---

## Phase 6: Transport and client shell

- [ ] T030 Expose the agent over AG-UI in `agent/server.py`.
- [ ] T031 Scaffold the React client in `ui/` with the transport client and a session id
  that survives a reload.
- [ ] T032 Implement the design system in `ui/src/styles/`: graphite ground, one accent,
  hairline rules, strict grid, tabular figures as the global default for numerals.

---

## Phase 7: Dynamic surfaces (US2, US5)

- [ ] T033 Define the component catalog in `ui/src/a2ui/` with schema backed definitions
  and renderers.
- [ ] T034 Build the catalogue surface: ranked cards, headline specifications, score bar,
  and an expansion revealing the reasoning panel and the cost of ownership table.
- [ ] T035 Build the reasoning panel from score data only: per dimension bars, dominant
  factors, quantified runner up comparison. Satisfies FR-022 and FR-023.
- [ ] T036 Implement weight adjustment re-ranking in place through data model updates,
  with the bars animating to their new values. Satisfies FR-020.
- [ ] T037 Build the progress surface: slot checklist with inferred values distinguished,
  current phase, resolving filter counts, streaming tool calls. Satisfies US5.
- [ ] T038 Verify both surfaces update incrementally rather than by replacement.
  Satisfies FR-034.

---

## Phase 8: MCP Apps (US3, US4)

- [ ] T039 Build the `formular` MCP server in `mcp/formular/` with a tool declaring
  `_meta.ui.resourceUri` and serving the surface as a `ui://` resource.
- [ ] T040 Build the form surface with purchase and rental variants, client side
  validation and bridge submission, bundled to a single HTML file.
- [ ] T041 Write submitted values into session state and continue the conversation in
  thread. Satisfies FR-026.
- [ ] T042 Build the `kasse` MCP server in `mcp/kasse/`.
- [ ] T043 Build the checkout surface: itemised summary with tax at nineteen percent as a
  separate line, contract confirmation, payment reference, invalid bank identifier, and no
  card input in the component set at all.
- [ ] T044 Implement the simulation indicators: persistent banner, document watermark, and
  the token inside every reference. Satisfies FR-030.
- [ ] T045 [P] Test the checkout surface markup in `tests/test_kasse.py`: indicators
  present, tax line separated, no card input present in any state. Satisfies SC-011.
- [ ] T046 Attach the MCP Apps middleware and confirm both surfaces render in chat.

---

## Phase 9: Observability

- [ ] T047 Wire OpenTelemetry and Langfuse in `agent/observability.py`, instrumented at
  startup.
- [ ] T048 Attach ranking tool inputs and outputs to spans so a recommendation traces back
  to its scores. Satisfies FR-035.

---

## Phase 10: Evaluation

- [ ] T049 Write twenty personas in `evals/personas.json`, each with a hidden ground truth
  need and the constraints its recommendations must satisfy.
- [ ] T050 Build the harness in `evals/run_evals.py` running each persona programmatically.
- [ ] T051 Score slot filling completeness, hard constraint violations deterministically,
  rationale faithfulness by model judgement, and turns to complete state.
  Satisfies FR-037 and FR-038.
- [ ] T052 Run the suite and commit results to `evals/results/`.

---

## Phase 11: Delivery

- [ ] T053 Write the `Dockerfile` set and `docker-compose.yml` bringing up agent, MCP
  servers and client from one command. Satisfies SC-012.
- [ ] T054 Verify a cold start on a clean checkout holding only an API key.
- [ ] T055 Write `README.md`: description, screenshots, quickstart, architecture, how
  ranking works, how to run the evaluations, the results table, project structure.
- [ ] T056 [P] Write `docs/architecture.md`.
- [ ] T057 Produce the slide deck against the organisers' template.
- [ ] T058 Script and record the demonstration video covering an inference being confirmed,
  the live progress surface, the ranked catalogue, a reasoning panel, the form in chat, the
  simulated checkout with its banner visible, and a reload proving persistence.
- [ ] T059 Walk the mandatory requirement table and name the file satisfying each row.

---

## Dependencies

- Phase 0 gates phases 7 and 8. Everything else may proceed regardless of its outcome.
- Phase 2 gates phase 3. Phase 3 gates phases 4 and 7.
- Phase 4 gates phases 5, 6, 9 and 10.
- Phases 2 and 3 carry no dependency on an API key and proceed while key access is
  arranged.
- Within a phase, tasks marked [P] touch distinct files and may proceed in any order.
