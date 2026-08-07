# Implementation Plan: fahrbereit, a conversational car buying and rental advisor

**Branch**: `001-fahrbereit-agent` | **Date**: 2026-08-07 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-fahrbereit-agent/spec.md`

## Summary

A Python agent session, built on the Claude Agent SDK, drives a five phase state machine
over a typed interview record: interview, search, score, present, transact. Marketplace
search, ranking and cost of ownership are ordinary Python functions exposed to the model
as tools, so every number the user sees is computed before it is described. The model's
role is to elicit, to infer, and to narrate.

Two interactive surfaces are MCP Apps rendered inside the conversation: the intake form
and the simulated checkout. Two further surfaces are dynamic agent driven interfaces
defined against a bring your own component catalog: the ranked catalogue and the live
progress panel. Transport between the Python agent and the React client is the AG-UI
event stream. Traces go to Langfuse over OpenTelemetry.

The marketplace is a seeded generated dataset of German listings, committed to the
repository, reproducible byte for byte from its generator.

## Technical Context

**Language/Version**: Python 3.12 for the agent and tools; TypeScript with React 18 for
the client and the app surfaces.

**Primary Dependencies**:

| Concern | Choice | Version verified |
|---|---|---|
| Agent runtime | `claude-agent-sdk` (`ClaudeSDKClient`) | 0.2.132 |
| Agent to client transport | `ag-ui-claude-sdk` | 0.1.5 |
| MCP surfaces in chat | `@ag-ui/mcp-apps-middleware` | 0.0.3 |
| MCP App authoring | `@modelcontextprotocol/ext-apps` | 1.7.5 |
| MCP server authoring | `mcp` (Python) | 2.0.0 |
| Dynamic interface renderer | `@copilotkit/a2ui-renderer` | 1.66.4 |
| Single file app bundling | `vite-plugin-singlefile` | 2.3.3 |
| Tracing | `openinference-instrumentation-claude-agent-sdk`, `langfuse` | 0.1.9, 4.14.3 |

**Storage**: SQLite on a mounted volume, one row per session holding the serialised
state document. Chosen over loose JSON files for atomic writes under concurrent tab
updates, and over a server database because the deliverable must start from one command
with no external service.

**Testing**: `pytest` for the deterministic core, which is where the risk is. Ranking,
filtering, cost of ownership, state transitions and dataset invariants are unit tested.
The interactive surfaces are covered by the persona harness and by assertions over the
rendered app markup rather than by a browser automation suite, which does not repay its
setup cost inside the time budget.

**Target Platform**: Linux containers behind `docker compose`; the client is a modern
evergreen browser.

**Project Type**: Web application, Python backend and React frontend, plus three MCP
servers and a committed data artifact.

**Performance Goals**: Hard filter and score over the full dataset in under fifty
milliseconds, so that weight adjustment re-ranks without a perceptible wait. First
interview response streaming within two seconds.

**Constraints**: No network dependency on any listing source. No payment integration in
any environment. Deterministic ranking. Dataset regeneration must be reproducible.

**Scale/Scope**: Roughly three hundred listings, ten categories, twenty evaluation
personas, four interactive surfaces, one user per session.

## Constitution Check

*GATE: passed before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | How this plan satisfies it | Gate |
|---|---|---|
| I. Deterministic decisions, narrated | Filtering, scoring and cost of ownership live in `agent/tools/` as pure functions with unit tests. The model receives their output as tool results and is instructed to narrate rather than compute. Score data is persisted with the recommendation so prose can be checked against it. | Pass |
| II. Protocols used properly | `formular` and `kasse` are real MCP servers whose tools declare `_meta.ui.resourceUri`; their surfaces are `ui://` resources bundled to single HTML files and driven over the `ui/` bridge. Catalogue and progress use a registered component catalog and incremental update messages. Phase 0 spike proves the render path before any surface is designed. | Pass, contingent on spike |
| III. Simulation never ambiguous | `kasse` has no card input in its component set at all, which makes the violation impossible rather than merely avoided. Banner, watermark and the SIMULATION token in every reference are asserted by test. | Pass |
| IV. State server side, typed, revisable | Pydantic models in `agent/state.py`, SQLite persistence keyed by session id, per slot provenance, and an explicit dependency graph that maps a revised slot to the artifacts it invalidates. | Pass |
| V. Verified, not asserted | Spike outcomes are written down before the architecture is trusted. Dataset floors, score arithmetic and constraint satisfaction are checked by automated tests rather than by inspection. A requirement to file mapping is produced before completion is claimed. | Pass |
| Data and IP constraints | Generator invents every dealer and operator name from a committed word list; a test asserts no real operator name appears. No BMW asset enters the tree. | Pass |
| Interface discipline | A single stylesheet defines the graphite ground, the one accent, hairline rules and `font-variant-numeric: tabular-nums` as a global default for numeric cells. | Pass |

No violations to record in Complexity Tracking.

## Phase 0: Research and de-risking

Detailed in [research.md](./research.md). Two questions must be answered before the
architecture is trusted:

1. Does the MCP Apps middleware render an app surface in chat when the agent backend is an
   external Claude Agent SDK endpoint rather than an in-process built in agent? Fallbacks,
   in order of preference: a Node proxy hosting the middleware in front of the Python
   endpoint, then hosting the app bridge directly in the React client and fetching the
   `ui://` resource over our own MCP client.
2. Does a non-trivial dynamic component, a car card with image, spec table and action,
   render end to end from an agent emitted message against a custom catalog?

Both outcomes are recorded in `docs/spike-notes.md` before implementation begins, and the
spike code is discarded rather than merged.

## Phase 1: Design

- [data-model.md](./data-model.md): the typed state record, listing and rental schemas,
  score and cost of ownership structures, and the slot to artifact invalidation map.
- `contracts/`: the tool signatures the agent may call, and the MCP App bridge message
  shapes for form submission and checkout completion.

## Build order

Sequenced so that each stage is demonstrable on its own and the highest risk work happens
while there is still time to fall back.

1. **Spikes** (Phase 0). Prove the two render paths. Record and discard.
2. **Data**. Generator, dataset, invariant tests. Everything downstream needs inventory,
   and it has no dependencies of its own.
3. **Deterministic core**. State models and persistence, hard filter, scoring, cost of
   ownership, with unit tests. This is the differentiator and it is testable without a
   model, an interface, or a key.
4. **Agent session**. Tools registered in process, system prompt and interview policy,
   phase machine, persistence wiring. First end to end conversation in a terminal.
5. **Marketplace MCP server** (`markt`). Wraps the search functions in the protocol.
6. **Transport and client shell**. AG-UI endpoint, React chat, the design system.
7. **Dynamic surfaces**. Component catalog, catalogue surface, progress surface.
8. **MCP Apps**. `formular`, then `kasse`, each bundled to a single file and wired through
   the middleware.
9. **Observability**. Instrumentation at startup, ranking inputs and outputs on spans.
10. **Evaluation**. Personas, harness, results table.
11. **Delivery**. Containers, compose, README, deck, video.

Stages two and three carry no dependency on an API key, so they proceed while key access
is being arranged.

## Project Structure

### Documentation (this feature)

```text
specs/001-fahrbereit-agent/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 decisions and spike outcomes
├── data-model.md        # Phase 1 entity design
├── contracts/           # Tool and bridge message contracts
└── tasks.md             # Phase 2 task breakdown
```

### Source Code (repository root)

```text
agent/
├── session.py           # ClaudeSDKClient orchestration and phase machine
├── state.py             # Typed interview state, provenance, invalidation
├── store.py             # SQLite session persistence
├── observability.py     # OpenTelemetry and Langfuse wiring
├── prompts/             # System prompt and interview policy
└── tools/
    ├── search.py        # Marketplace query and availability
    ├── ranking.py       # Hard filter and weighted scoring
    └── tco.py           # German five year cost of ownership

mcp/
├── markt/               # Marketplace MCP server
├── formular/            # Intake form MCP App
└── kasse/               # Simulated checkout MCP App

ui/
└── src/
    ├── a2ui/            # Component catalog, definitions, renderers
    ├── chat/            # Conversation shell and transport client
    └── styles/          # Design system

data/
├── generate.py          # Seeded deterministic generator
└── listings.json        # Committed dataset

evals/
├── personas.json
├── run_evals.py
└── results/

tests/                   # pytest over the deterministic core
docs/
├── spike-notes.md
└── architecture.md
```

**Structure Decision**: backend and frontend are separated because they are separate
runtimes, and the MCP servers sit beside both because they are consumed by the agent but
render into the client. The German submodule names are kept throughout, including in
container names and tool namespaces, so that a reader tracing a tool call from a trace
span to a source file follows one vocabulary.

## Complexity Tracking

> No constitution violations require justification.
