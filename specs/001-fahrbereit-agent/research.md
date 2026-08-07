# Phase 0: Research and de-risking

**Feature**: 001-fahrbereit-agent | **Date**: 2026-08-07

## Settled decisions

### Marketplace data: generate, do not scrape

**Decision**: build a seeded generator producing a committed dataset of German listings.

**Rationale**: the two marketplaces a German buyer would actually use, mobile.de and
AutoScout24, publish no free public API. Scraping them inside a two day build carries a
legal exposure and a reliability exposure at the same time, and a demo that depends on a
live scrape fails in front of an audience for reasons unrelated to the work. A generated
dataset is reproducible, is available offline, and can be shaped to exercise every branch
of the ranking model on purpose.

**Alternatives rejected**: scraping, for the reasons above. A public used car dataset from
a data science repository, rejected because those are almost all American, priced in
dollars, and carry none of the German regulatory fields, emissions class, environmental
badge, next inspection date, that make the ranking model worth building.

**Consequence**: coherence becomes our responsibility. Price must fall with age and
mileage, power must track engine and trim, consumption must track power and body. An
incoherent dataset is visible at a glance and would undermine the ranking work it feeds.

### Ranking: deterministic computation, model narration

**Decision**: a two stage pipeline in Python, a boolean hard filter followed by a weighted
sum over named dimensions, exposed to the agent as a tool.

**Rationale**: a recommendation is a claim about someone's money. It has to be auditable,
reproducible, and explainable by pointing at arithmetic. A model asked to rank directly
produces an ordering nobody can check and that changes between runs. Separating the two
also lets the weights become a user facing control, which turns the ranking from an
opaque verdict into an instrument.

**Alternatives rejected**: model ranking with a structured output schema, rejected because
it is not reproducible and cannot be unit tested. A learned ranker, rejected because there
is no training data and no time to produce any.

### State: SQLite, server side, provenance per slot

**Decision**: Pydantic models serialised into a SQLite table keyed by session id.

**Rationale**: the requirement is survival across a page reload and a process restart,
which rules out client state and in-memory state. SQLite gives atomic writes, which
matters when two tabs share a session, and it needs no service to be running, which
matters when the deliverable must start from a single command.

**Alternatives rejected**: JSON files per session, rejected for torn writes under
concurrent updates. Redis or Postgres, rejected because adding a service to the compose
file for a single small document is cost without benefit.

### Transport: AG-UI over a bespoke event protocol

**Decision**: `ag-ui-claude-sdk`, the official bridge between the Claude Agent SDK and the
AG-UI event stream.

**Rationale**: the MCP Apps middleware and the dynamic interface renderer both expect
AG-UI events. Inventing a socket protocol would mean reimplementing the surface plumbing
on both sides for no gain.

### Tools: in-process where pure, MCP where protocol matters

**Decision**: search, ranking and cost of ownership are registered in process through the
SDK's tool decorator and an in-process server. The marketplace is additionally exposed as
a standalone MCP server, and the two interactive surfaces are MCP servers by requirement.

**Rationale**: pure Python functions do not benefit from subprocess isolation, and each
subprocess is another failure mode during a live demo. The marketplace server is built
anyway because the incremental cost is small once the MCP plumbing exists and it
demonstrates server authorship alongside app authorship.

## Open questions carried into the spike

Two integration paths in the chosen stack are unverified. Neither can be settled by
reading documentation, and both change the architecture if they fail, so both are proven
before any surface is designed. Outcomes are recorded in `docs/spike-notes.md`.

### Spike 1: MCP App rendering behind an external agent endpoint

**Question**: does `MCPAppsMiddleware` render an app surface in the chat when the agent
backend is an external Claude Agent SDK endpoint rather than an in-process built in agent?

**Method**: one MCP server exposing one tool whose description carries
`_meta.ui.resourceUri`; one hello world single file HTML surface behind that URI; one
Claude Agent SDK session; one React page. Success is the surface rendering inside the chat
with a button click round tripping to the server.

**Fallbacks, in order**: a Node process hosting the middleware in front of the Python
endpoint; failing that, instantiating the app bridge directly in the React client and
fetching the `ui://` resource over our own MCP client. Both keep the protocol intact and
cost only build time.

**Status**: not yet run. Requires an API key, which is not present in the build
environment as of 2026-08-07. Flagged as the first blocker.

### Spike 2: non-trivial dynamic component from an agent emitted message

**Question**: does a car card carrying an image, a specification table and an action
render end to end from an agent emitted message against a custom component catalog, and
does the surface update, component update, data model update, begin rendering flow behave
as documented?

**Method**: register one component definition against a schema, emit one message from the
agent, assert the card renders and that a subsequent data model update changes a value in
place without a full re-render.

**Status**: not yet run. Blocked on the same key.

## Risk register

| Risk | Impact | Mitigation |
|---|---|---|
| Spike 1 fails and both fallbacks are slow | Two mandatory requirements at risk | Spike first, timeboxed. Fallbacks identified in advance so the decision is a choice, not a search. |
| API key unavailable | Nothing that involves the model can be verified | Build the key independent core first: dataset, filtering, scoring, cost of ownership, state, all unit tested without a model. |
| Dataset reads as fake | Undermines the credibility of the ranking that consumes it | Correlated generation, German trade fields, invariant tests including a price monotonicity check within a model line. |
| Simulated checkout mistaken for real | Safety failure and a specification violation | No card input exists in the component set. Banner, watermark and token asserted by test rather than by review. |
| Model narrates numbers it was not given | Faithfulness failure, the central claim of the project | Prose is generated only from a score breakdown already in state, and faithfulness is measured across the persona suite. |
