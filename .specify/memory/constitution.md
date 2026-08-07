# fahrbereit Constitution

fahrbereit is a multistep conversational agent that helps a person in Germany choose a
car to buy or rent. It interviews, researches a marketplace, ranks with an auditable
model, and closes the loop with an in-chat intake form and a simulated checkout.

These principles bind every contributor and every generated artifact. Where a principle
conflicts with convenience, the principle wins.

## Core Principles

### I. Deterministic Decisions, Narrated by the Model

Ranking, filtering, and total cost of ownership are computed in plain Python and are
reproducible from inputs alone. The language model reads those numbers and explains
them; it never produces them. Any recommendation shown to a user MUST be traceable to a
score breakdown that exists in state before the explanation is written. A rationale that
cannot be reconciled against its score data is a defect, not a stylistic issue.

Rationale: a judge, a user, or a regulator can audit arithmetic. None of them can audit
an unexplained preference.

### II. Protocols Used Properly, Not Decoratively

The interactive surfaces are built on their intended protocols and use their real
message flows. MCP Apps are declared through `_meta.ui.resourceUri`, served as `ui://`
resources, and communicate over the `ui/` JSON-RPC bridge. A2UI surfaces update through
`updateComponents` and `updateDataModel` against a registered component catalog. Static
HTML masquerading as a dynamic surface, or a re-rendered blob masquerading as an
incremental update, does not satisfy this project.

Rationale: the point of the exercise is protocol fluency. A shortcut that produces the
same pixels produces none of the value.

### III. Simulation Is Never Ambiguous

No real payment rail, no real card field, no real bank identifier, not even disabled or
placeholder ones. The checkout surface carries a persistent banner, a watermark on every
generated document, and the literal token `SIMULATION` inside every contract reference
and payment reference. There MUST be no scroll position, no screenshot, and no printed
artifact of this system in which a reasonable person could believe money moved.

Rationale: an ambiguous mock is worse than no mock. This is a hard safety line, and it
is cheaper to over-signal than to explain afterwards.

### IV. State Is Server-Side, Typed, and Revisable

Interview state is a typed structure persisted server-side against a session id and
survives a page refresh. Every slot records whether it was stated by the user or
inferred by the agent, and inferred values are visibly marked and correctable. Revising
an answer invalidates exactly the downstream results that depended on it and nothing
more. The agent MUST NOT ask for information already present in state or safely
derivable from it.

Rationale: an agent that forgets is a demo. An agent that remembers, shows its
inferences, and lets you correct them is a product.

### V. Verified, Not Asserted

A capability is complete when it has been executed and observed, not when the code that
should provide it has been written. Claims of working integrations require a run. Every
mandatory requirement maps to a named file, and that mapping is checked before any
completion is reported. Constraint satisfaction in evaluation is measured
deterministically, never by asking a model whether it did well.

Rationale: the failure mode of fast agentic development is confident, untested
integration. The counter is a habit of proof.

## Data and Intellectual Property Constraints

The marketplace is a generated mock, produced by a seeded deterministic generator
committed to the repository. No scraping of live marketplaces, and no dependency on any
third-party listing API.

Manufacturer names are used as factual references to real vehicles and are permitted.
Every dealer, rental operator, and marketplace brand in the dataset MUST be invented.
Real dealership groups and real rental companies MUST NOT appear. No BMW Group mark,
logo, typeface, colour identity, or trade dress appears anywhere in the product or its
documentation.

Generated data MUST be internally coherent. Price, age, mileage, power, and equipment
level correlate the way they do in the German used-car market; an older, higher-mileage
car MUST NOT outprice a newer, lower-mileage car of the same model and trim.

## Interface Discipline

The interface is an instrument for reading vehicles, not an aesthetic in its own right.
Graphite ground, one restrained accent, hairline rules, a strict grid, generous
whitespace. Every number rendered anywhere in the product uses tabular figures so
columns align. No gradients, no glassmorphism, no glow, no drop shadows on cards. Motion
appears only where it communicates a state change.

No emoji anywhere in the repository, the interface, the documentation, or the commit
history. No em dashes in any code comment, document, README, commit message, or
interface string; use a comma, a colon, a semicolon, or a restructured sentence.

## Development Workflow

Specification precedes implementation. The spec-kit chain runs in order and every
artifact is committed before the code it governs.

Commits are continuous and scoped: one coherent, independently readable change per
commit, in imperative mood with a scoped prefix, targeting roughly one commit per unit
of completed work. Commit history is treated as evidence of process, so batching
unrelated work or landing the project in a single late commit is a violation regardless
of code quality.

Secrets are never committed. Required environment variables are documented in
`.env.example` with placeholder values only.

Blockers that threaten a mandatory requirement are surfaced immediately rather than
worked around silently.

## Governance

This constitution supersedes contributor preference and tooling defaults. Amendments are
made by editing this file in a dedicated commit that states what changed and why, and by
propagating the change to any spec, plan, or task artifact it invalidates.

Compliance is checked at three gates: before planning, before implementation, and before
any claim of completion. A change that violates a principle is reworked or the principle
is amended in the open; it is not waived quietly.

**Version**: 1.0.0 | **Ratified**: 2026-08-07 | **Last Amended**: 2026-08-07
