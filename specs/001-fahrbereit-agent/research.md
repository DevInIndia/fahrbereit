# Phase 0: Research and de-risking

**Feature**: 001-fahrbereit-agent | **Date**: 2026-08-07

This is a decision log. Superseded decisions are kept in place and marked, with the
decision that replaced them recorded underneath. Nothing is deleted to make the record
look tidier than the process was.

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

**Superseded on 2026-08-07 by the harness change recorded below.** The choice of AG-UI as
the transport survives; only the bridge package changed, from `ag-ui-claude-sdk` to
`ag-ui-langgraph`. The reasoning below still applies.

**Decision**: `ag-ui-claude-sdk`, the official bridge between the Claude Agent SDK and the
AG-UI event stream.

**Rationale**: the MCP Apps middleware and the dynamic interface renderer both expect
AG-UI events. Inventing a socket protocol would mean reimplementing the surface plumbing
on both sides for no gain.

### Tools: in-process where pure, MCP where protocol matters

**Partially superseded on 2026-08-07.** The principle is unchanged. The mechanism changed
from the Claude Agent SDK's tool decorator to LangChain tools passed to
`create_deep_agent(tools=[...])`.

**Decision**: search, ranking and cost of ownership are registered in process through the
SDK's tool decorator and an in-process server. The marketplace is additionally exposed as
a standalone MCP server, and the two interactive surfaces are MCP servers by requirement.

**Rationale**: pure Python functions do not benefit from subprocess isolation, and each
subprocess is another failure mode during a live demo. The marketplace server is built
anyway because the incremental cost is small once the MCP plumbing exists and it
demonstrates server authorship alongside app authorship.

## Decision 2026-08-07: agent harness changed to LangChain DeepAgents

**Status**: supersedes the Claude Agent SDK choice recorded in plan.md and in the
constitution as originally ratified.

**Decision**: the agent harness is LangChain DeepAgents (`deepagents`), pointed at a chat
model supplied through a configuration selected factory. The first configured provider is
Google Gemini through Google AI Studio.

**Rationale**: the project acquired a hard constraint that it must cost nothing to build
or to run, with no billing relationship attached to any dependency. The Anthropic API
sells prepaid credits and offers no free tier, so the Claude Agent SDK cannot be pointed
at a model without someone paying. The hackathon brief permits three harnesses, Claude
Agent SDK, LangChain DeepAgents and the OpenAI Agents SDK. DeepAgents is the one of the
three that is model agnostic by construction, so it satisfies the brief and the budget at
the same time.

**Rejected: Claude Pro or Max subscription OAuth for the agent runtime.** Anthropic's
February 2026 policy prohibits subscription authentication for third party products,
including through the Agent SDK. Judges running our submission is third party use, so this
route would put the submission out of compliance at exactly the moment it is evaluated.
Rejected on policy grounds rather than on technical ones. This is worth stating plainly
because the route is otherwise attractive and someone will ask why it was not taken.

**Rejected: OpenAI Agents SDK.** Permitted by the brief and usable against
OpenAI compatible free endpoints, but it carries the same shape of problem as the Claude
SDK, a harness whose defaults assume one vendor, and it offers nothing DeepAgents does not
for this workload.

**Rejected: keeping the Claude Agent SDK and asking judges to supply a key.** Shifts our
cost onto the evaluator and makes the submission unrunnable by default. A submission that
does not start is not a submission.

**What the change costs us**: the Claude Agent SDK work committed so far is specification
only, so no implementation is discarded. The bridge package changes and the tool
registration mechanism changes. Both were named but unwritten.

**What the change gains us**, all verified against the installed packages rather than
against documentation:

- `create_deep_agent` accepts `model` as either a provider string or a `BaseChatModel`
  instance. The object form is what makes a provider factory possible without the agent
  importing any provider.
- `create_deep_agent` accepts `checkpointer`, a LangGraph `BaseCheckpointSaver`. Session
  persistence for M-7 becomes a supported feature of the harness rather than something
  bolted to the side of it.
- `create_deep_agent` accepts `interrupt_on`, which is the natural mechanism for pausing
  on the intake form and on checkout.
- `ag_ui_langgraph` exports first party A2UI helpers: `get_a2ui_tools`, `a2ui_tool`,
  `A2UIGuidelines`, `A2UIToolParams`, `BASIC_CATALOG_ID` and `A2UI_OPERATIONS_KEY`, plus
  `add_langgraph_fastapi_endpoint` for the server wiring.

### Verified package state, 2026-08-07

Read from the index and from the installed distributions, not from documentation.

| Package | Version | Note |
|---|---|---|
| `deepagents` | 0.7.5 | Requires Python 3.11 or newer. |
| `langchain` | 1.3.14 | |
| `langgraph` | 1.2.10 | |
| `langchain-google-genai` | 4.3.2 | A declared dependency of `deepagents`, not an add on. |
| `ag-ui-langgraph` | 0.0.42 | Python. Needs `fastapi`, which is not a declared dependency. |
| `@ag-ui/langgraph` | 0.0.42 | Versioned in lockstep with the Python package. |
| `@ag-ui/mcp-apps-middleware` | 0.0.3 | Unchanged by the pivot. |
| `@copilotkit/a2ui-renderer` | 1.66.4 | Unchanged by the pivot. |
| `@modelcontextprotocol/ext-apps` | 1.7.5 | Unchanged by the pivot. |

Two corrections worth recording, because both would have produced wrong code:

1. The PyPI JSON endpoint served `0.4.11` as the latest `deepagents` release while the
   package index served `0.7.5`. The index is correct. Metadata from a single source was
   not trusted.
2. The DeepAgents overview documentation states that models are passed as string
   identifiers and not as model objects. The installed signature accepts both. The
   documentation is wrong on the exact point our provider abstraction depends on.

### Effect on the two protocol requirements

The change makes both requirements easier rather than harder, which is the opposite of
what was feared when the pivot was proposed.

**MCP Apps**: `MCPAppsMiddleware` is a TypeScript middleware that operates on the AG-UI
event stream and is not bound to any particular agent backend. The topology it documents
is a frontend talking to a Node process running the middleware, which fronts a Python
AG-UI endpoint, with no Python side changes required. LangGraph is named as one of the
supported AG-UI Python integrations. The Node proxy that was written down as the *first
fallback* for spike A under the Claude Agent SDK is, under this stack, the *documented*
topology. The risk that spike A was designed to measure is materially lower.

**A2UI**: previously this depended on the renderer and an agent able to emit the right
messages, with the emission side unproven. `ag_ui_langgraph` now supplies the emission
side directly. The underlying `ag_ui_a2ui_toolkit` provides a framework neutral shape with
per framework factories, so the catalog, surface id and guidelines are configuration
rather than hand rolled message construction.

## Decision 2026-08-07: model provider selected by configuration

**Decision**: nothing outside `agent/model/` knows which model vendor is in use. A factory
reads `MODEL_PROVIDER` and returns a `BaseChatModel`. `create_deep_agent` receives that
object. Adding a vendor means adding one class and one configuration value.

**Rationale**: the free tiers we are relying on are the least stable part of the stack.
They can be rate limited, deprecated, or restricted without notice, and we have no
commercial relationship that would give us warning or recourse. The cost of the seam is
about twenty lines. The cost of not having it, discovered at hour 30, is a refactor
through the agent, the session and the tests at once. This is the same reasoning that put
the payment provider seam at Milestone 1.

**Providers**: `gemini` is the default and the only one configured at the outset.
`cerebras` and `groq` are the identified fallbacks. Both expose OpenAI compatible
endpoints and are free without a credit card, so both are reachable through
`ChatOpenAI` with a `base_url` override rather than needing a new client library. This is
why the seam returns a `BaseChatModel` rather than a vendor specific handle.

**Not yet verified**: the Cerebras and Groq free tier terms, and that
`ChatOpenAI` with a `base_url` override works against them for tool calling
specifically. Tool calling is the capability this agent lives on, and OpenAI compatible
endpoints vary in how completely they implement it. These are recorded as unproven and
must be tested before either is relied upon in a demonstration.

## Decision 2026-08-07: zero cost constraint and dependency audit

Every dependency was checked for a billing relationship.

| Dependency | Cost | Basis |
|---|---|---|
| Google AI Studio, Gemini | Free tier, no card | Google states the free tier requires no billing account and applies to an active project. |
| `deepagents`, `langchain`, `langgraph`, all PyPI packages | Free, open source | |
| All npm packages | Free, open source | |
| `langsmith` | Free, and inert | A hard dependency of `deepagents`, so it cannot be removed. Verified by execution that `tracing_is_enabled()` returns false with no environment configured, so no account is required and nothing is transmitted unless we opt in. |
| Langfuse Hobby | Free, no card | Retained. Also self hostable, which is the fallback if the hosted tier changes. |
| Docker Engine, Docker Compose | Free | Docker Desktop licensing is free for individuals and small organisations, which covers this use. |
| Hosting, if we deploy publicly | See below | |

**Deployment, if we go past shipping a container.** The candidate is Hugging Face Spaces
with the Docker SDK, which is free and needs no card. Two constraints are confirmed from
its configuration reference and both affect us:

- A Space exposes a **single port**, `app_port`, defaulting to 7860. Our compose file has
  several services, so a public deployment needs either one combined image or a reverse
  proxy inside one container. This is a real packaging difference from the local compose
  setup, not a detail.
- **Persistent storage is no longer offered.** Session state written to SQLite would not
  survive a Space restart. M-7 is still satisfied locally, where the requirement is a page
  reload and a process restart, but a public deployment would need its persistence claim
  stated honestly or backed by something external.

Public deployment is optional under the brief. It is not scheduled ahead of any mandatory
item, and these constraints are the reason it is not treated as free work.

## Resolved 2026-08-08: Gemini free tier rate limits, verified

**Source**: the Google AI Studio rate limit dashboard, `https://aistudio.google.com/rate-limit`,
read against this project's own key on 2026-08-08. These are project specific and
authenticated; they are not published in Google's public documentation. Re-check before
relying on them at a later date.

| Model | RPM | TPM | RPD |
|---|---:|---:|---:|
| Gemini 2.5 Flash | 5 | 250,000 | 20 |
| Gemini 3 Flash | 5 | 250,000 | 20 |
| Gemini 3.5 Flash | 5 | 250,000 | 20 |
| Gemini 3.6 Flash | 5 | 250,000 | 20 |
| Gemini 2.5 Flash Lite | 10 | 250,000 | 20 |
| **Gemini 3.1 Flash Lite** | **15** | **250,000** | **500** |
| **Gemini 3.5 Flash Lite** | **15** | **250,000** | **500** |
| Gemma 4 31B | 30 | 16,000 | 14,400 |
| Gemma 4 26B | 30 | 16,000 | 14,400 |
| Gemini 2.5 Pro | 0 | 0 | not available |
| Gemini 3.1 Pro | 0 | 0 | not available |

**The full Flash models are unusable.** Twenty requests per day is roughly three user
turns at this system's call volume. Nothing on the primary path may depend on them, and
the Pro models are not on the free tier at all.

**Decision**: the primary reasoning model is `gemini-3.5-flash-lite`, at 15 RPM and 500
RPD. `gemini-3.1-flash-lite` carries identical limits and serves as the alternate, which
also means the two together provide a thousand requests per day if the load is split.

### Verified model identifiers

Resolved by listing models against our key rather than by guessing. Fifty eight models
were returned; these are the relevant ones, and note that the Gemma identifiers carry an
`-it` suffix that the dashboard names omit.

| Role | Identifier |
|---|---|
| Primary reasoning | `gemini-3.5-flash-lite` |
| Alternate reasoning | `gemini-3.1-flash-lite` |
| Bulk and offline | `gemma-4-31b-it` |
| Bulk alternate | `gemma-4-26b-a4b-it` |

Gemma models advertise only `generateContent` and `countTokens`. They do not support
`createCachedContent`, so no prompt caching is available on the bulk path.

## Superseded open question: Gemini free tier rate limits

**Resolved on 2026-08-08 by the verified table above.** Retained because it records why
the figures could not be sourced from documentation, which is the reason they must be
re-read from the dashboard rather than looked up.

**What was checked.** Google's official rate limit page,
`https://ai.google.dev/gemini-api/docs/rate-limits`, and its raw markdown twin at
`rate-limits.md.txt`. Neither contains a per model table of requests per minute, tokens
per minute or requests per day for any tier. The page carries only a spend based rate
limit table, a tier qualification table, and a batch enqueued token table, none of which
give the numbers needed here. The page states that limits depend on usage tier and can be
viewed in Google AI Studio, and links to `https://aistudio.google.com/rate-limit`.

**Conclusion**: Google no longer publishes free tier per model limits in public
documentation. They are behind an authenticated per project dashboard. There is no
official source to cite, which is why this section states an unknown rather than a figure.

**What the community reports**, recorded as unverified and not to be relied upon. Forum
threads on `discuss.ai.google.dev` report Gemini 2.5 Flash on the free tier at roughly 10
requests per minute, 250,000 tokens per minute and 250 requests per day. These are user
reports, not documentation.

**The figure of 1,500 requests per day** that prompted this direction appears to be from
an earlier era of the free tier, associated with Gemini 1.5 Flash and 2.0 Flash. It should
not be assumed to apply to Gemini 2.5 Flash.

### Why the requests per minute ceiling matters more than the daily one

A multistep agent turn is not one model call. A single user message in this system can
produce a planning call, one or more tool calling round trips for search and ranking, a
call to compose the narration, and an A2UI surface emission. Five to eight model calls per
user turn is a reasonable planning assumption.

If the ceiling really is 10 requests per minute, then a single user turn can consume most
of a minute's allowance, and a demonstrator speaking at a normal pace will hit the limit
live. That is a demonstration risk, not merely a throughput one. If the daily ceiling is
250 requests, the eight persona evaluation suite could exhaust a day's budget in one run,
which affects when and how often evaluations can be run.

### Mitigations, in order of preference

1. **Reduce calls per turn.** Fewer, larger tool calling round trips; do not emit a
   surface update per token; avoid subagent delegation on the demonstration path. This is
   worth doing regardless of the limit and costs nothing.
2. **Route by task.** Use a smaller and more generously limited model for narration and
   for slot extraction, reserving the stronger model for planning. The provider seam makes
   this a configuration matter.
3. **Cache and replay for demonstrations.** A recorded session that can be replayed
   without live calls removes the demonstration risk entirely. This must be labelled as a
   replay if it is ever shown, and never presented as a live run.
4. **Switch providers.** Cerebras or Groq through the same seam, if either proves to have
   a more workable free ceiling.
5. **Batch and pace the evaluation suite** so that it fits inside a daily budget, running
   overnight if necessary.

### To resolve this

The numbers must be read from the AI Studio rate limit dashboard for the actual project
once a key exists, and written into this section with the date they were observed. Until
then no planning decision may depend on a specific figure.

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
| Free tier requests per minute ceiling throttles a live demonstration | The demonstration is the submission. Throttling mid demonstration is highly visible. | Unknown ceiling, see the open question above. Reduce calls per turn, route narration to a cheaper model, and treat throttling as a visible state rather than an error. Measured in spike 0 before anything depends on it. |
| Free tier terms change or the tier is withdrawn mid build | Total loss of model access | Provider seam, so switching is a configuration change. Cerebras and Groq identified, though neither is yet verified for tool calling. |
| Gemini tool calling proves unreliable for multistep work | The agent cannot function; the harness choice would need revisiting | Spike 0 tests multi tool calling explicitly before any agent work begins. |
| A2UI helpers in `ag_ui_langgraph` are pre 1.0 and may churn | Rework on the catalogue and progress surfaces | Version pinned exactly. The renderer side is independent and stable at 1.66.4. |
