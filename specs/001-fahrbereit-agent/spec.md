# Feature Specification: fahrbereit, a conversational car buying and rental advisor

**Feature Branch**: `001-fahrbereit-agent`

**Created**: 2026-08-07

**Status**: Draft

**Input**: User description: "A multistep AI agent that interviews a person about their
transport needs, researches a German car marketplace on their behalf, presents ranked
and explained recommendations, and completes an in-chat intake form and a simulated
checkout, holding state across every step."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Guided interview that infers rather than interrogates (Priority: P1)

A person arrives with a situation, not a specification. They say they drive two children
to school and make a monthly three hundred kilometre trip to their parents. The agent
derives family use, moderate annual mileage, and a need for rear seat and boot space,
shows those derivations as inferences, and asks the person to confirm or correct them
instead of asking cold questions it could have answered itself. It gathers the remaining
slots two questions at a time.

**Why this priority**: everything downstream reads from interview state. Without it there
is nothing to search, nothing to rank, and nothing to explain. It is also the first
thing a user experiences, so it carries the product's credibility.

**Independent Test**: run a scripted persona transcript against the agent with the
marketplace stubbed. Assert that the required slots are populated, that at least one slot
is marked as inferred rather than stated, and that no question repeats information
already present in state.

**Acceptance Scenarios**:

1. **Given** an empty session, **When** the user describes a family use case in free text,
   **Then** the agent populates the use case tag set with a family tag, marks it inferred,
   and asks the user to confirm rather than asking what the car is for.
2. **Given** a session where budget and intent are known, **When** the agent takes its next
   turn, **Then** it asks about neither budget nor intent.
3. **Given** any session turn, **When** the agent replies, **Then** it asks at most two
   questions.
4. **Given** a slot the agent filled by inference, **When** the user contradicts it,
   **Then** the slot is overwritten, re-marked as stated, and the contradiction does not
   recur later in the interview.

---

### User Story 2 - Ranked recommendations with auditable reasoning (Priority: P1)

With the interview complete, the agent searches the marketplace, applies the user's hard
constraints as a boolean filter, scores the survivors on named weighted dimensions, and
presents the top results as cards. Each card opens to reveal the score contribution per
dimension, the two or three factors that dominated, a five year cost of ownership table
computed for German conditions, and an explicit comparison against the runner up. The
weights are visible and the user can change them, which re-ranks the list in place.

**Why this priority**: this is the feature that distinguishes the product from a sort by
price. It is also the requirement most at risk of being faked by a model writing
plausible prose, so it must be built as computation with narration layered on top.

**Independent Test**: call the ranking tool directly with a fixed state object and a
fixed dataset. Assert the same ordering every run, assert that no returned listing
violates a hard constraint, and assert that the sum of dimension contributions equals the
reported total score.

**Acceptance Scenarios**:

1. **Given** a state with hard constraints, **When** ranking runs, **Then** every returned
   listing satisfies every hard constraint and the response reports how many listings each
   constraint eliminated.
2. **Given** an identical state and dataset, **When** ranking runs twice, **Then** the
   ordering and every score are identical.
3. **Given** a displayed recommendation, **When** the user expands the reasoning panel,
   **Then** the panel shows a per dimension breakdown whose contributions sum to the
   headline score.
4. **Given** a ranked list, **When** the user increases the weight on running costs,
   **Then** the list re-orders and the score bars animate to their new values without a
   full page reload.
5. **Given** a recommendation, **When** the agent states a reason in prose, **Then** each
   factual claim in that prose corresponds to a value present in the score data.

---

### User Story 3 - Booking details captured in chat, never in a redirect (Priority: P1)

The user picks a car. A structured form appears inside the conversation. For a purchase it
collects buyer details, cash or financing, whether a trade in is involved, and a preferred
collection date. For a rental it collects driver details, licence held since, the rental
window, an optional additional driver, and an insurance tier. It validates before it
submits, and on submission the values land in agent state and the conversation continues
in the same thread.

**Why this priority**: this is one of the two surfaces the brief requires to be an MCP
App, and it is the moment the conversation becomes a transaction. A redirect here would
break both the requirement and the product story.

**Independent Test**: render the form surface against a fixture selection, submit valid
and invalid payloads through the app bridge, and assert that invalid payloads are refused
client side and valid ones appear in persisted state.

**Acceptance Scenarios**:

1. **Given** a selected purchase listing, **When** the form renders, **Then** it shows
   purchase fields and no rental fields.
2. **Given** a selected rental listing, **When** the form renders, **Then** it shows rental
   fields including licence held since and insurance tier.
3. **Given** an invalid field, **When** the user submits, **Then** the form blocks
   submission and names the offending field.
4. **Given** a valid submission, **When** the user submits, **Then** the values are written
   to session state and the agent's next message reflects them.

---

### User Story 4 - A checkout that completes and is unmistakably simulated (Priority: P1)

The user reaches checkout inside the conversation. They see an order summary with value
added tax broken out at nineteen percent in the German invoice convention, a generated
contract reference, and for a rental the collection location, the collection window and
the deposit. A payment reference and an obviously false bank identifier stand in for a
transfer. A banner, a watermark, and the word SIMULATION inside the reference itself make
it impossible to read the screen as a completed payment.

**Why this priority**: the second mandatory MCP App, and the requirement with the sharpest
safety edge. A checkout that could be mistaken for real is a failure even if it functions.

**Independent Test**: render the checkout surface from a fixture order and assert the
presence of the simulation banner, the watermark, the SIMULATION token inside the
contract reference, the separated tax line, and the absence of any card input element.

**Acceptance Scenarios**:

1. **Given** a completed intake form, **When** checkout renders, **Then** the order summary
   lists net, tax at nineteen percent, and gross as separate lines.
2. **Given** any state of the checkout surface, **When** it is displayed or scrolled,
   **Then** a simulation notice is visible.
3. **Given** a completed checkout for a purchase, **When** the confirmation renders,
   **Then** it shows a watermarked purchase contract whose reference contains the token
   SIMULATION.
4. **Given** a completed checkout for a rental, **When** the confirmation renders, **Then**
   it shows a rental contract with collection location, collection window and deposit.
5. **Given** the checkout surface, **When** it is inspected, **Then** it contains no card
   number, expiry, or security code input, enabled or disabled.

---

### User Story 5 - Watching the agent work (Priority: P2)

While the agent interviews, searches and scores, a live surface shows what it is doing:
which slots are filled and which of those were inferred, the current phase, the filter
counts as the search resolves, and the tool calls as they stream.

**Why this priority**: it is the requirement that makes the system legible to an observer
rather than only to its user, and it satisfies the dynamic interface requirement together
with the catalogue. It is P2 only because the product still functions without it.

**Independent Test**: drive the agent through a scripted session and assert that the
surface receives incremental component and data model updates rather than a single
terminal render.

**Acceptance Scenarios**:

1. **Given** a running interview, **When** the agent fills a slot, **Then** the checklist
   updates and inferred slots are visually distinct from stated ones.
2. **Given** a running search, **When** filters resolve, **Then** the surface reports the
   candidate count and the exclusions per constraint.
3. **Given** any surface update, **When** it is transmitted, **Then** it is an incremental
   component or data model update rather than a replacement of the whole surface.

---

### User Story 6 - Revision without restart (Priority: P2)

Halfway through reading recommendations the user changes their budget, or decides they
want an automatic gearbox after all. The agent accepts the correction, invalidates only
the results that depended on it, keeps the rest of the interview, and re-runs the search.

**Why this priority**: it is the behaviour that separates a state machine from a
questionnaire, and it is directly graded through the state requirement. It sits below the
core path because the core path must work first.

**Independent Test**: populate a full state, mutate one slot, and assert that dependent
artifacts are invalidated while independent slots survive.

**Acceptance Scenarios**:

1. **Given** a completed ranking, **When** the user lowers the budget, **Then** the ranking
   is invalidated, the interview answers are retained, and a new ranking is produced.
2. **Given** a completed interview, **When** the user changes a hard constraint, **Then**
   the agent does not re-ask any slot that is still valid.

---

### User Story 7 - The session survives a refresh (Priority: P2)

The user reloads the page. The interview state, the current phase, the selected listing
and the ranking are all still there.

**Why this priority**: persistence is a stated requirement and is demonstrated in the
video. It is separable from the conversational logic.

**Independent Test**: write state, restart the backend process, read state back by session
id, and assert equality.

**Acceptance Scenarios**:

1. **Given** an in progress session, **When** the page reloads, **Then** the conversation
   and the filled slots are restored.
2. **Given** an in progress session, **When** the backend process restarts, **Then** state
   read by session id is unchanged.

---

### Edge Cases

- The hard filter eliminates every listing. The system reports which constraint was
  responsible, proposes the single relaxation that would recover the most candidates, and
  does not silently widen the search.
- The user states a budget that no listing in the chosen category can meet. The agent says
  so plainly with the observed price floor rather than presenting the least bad option as
  a recommendation.
- The user asks for a car type that does not exist in any category, or gives a location
  outside the dataset. The agent reports the mismatch rather than inventing inventory.
- The user changes intent from purchase to rental after a ranking exists. Category and use
  case survive; budget semantics, the ranking and any selection do not.
- The user abandons the session mid form. Reopening restores the partially filled form.
- Two browser tabs share a session id. The later write wins and the surface reflects the
  stored state on next update rather than diverging.
- The user tries to reach checkout without a completed intake form. The agent routes back
  to the form instead of producing a contract.
- The requested collection date falls outside a rental listing's availability. Availability
  is checked before checkout, not after.

## Requirements *(mandatory)*

### Functional Requirements

**Interview and state**

- **FR-001**: System MUST conduct a multi turn interview that elicits intent, use case,
  category preference, budget, target date, hard constraints, soft preferences and
  location.
- **FR-002**: System MUST record for every slot whether its value was stated by the user or
  inferred by the agent, and MUST expose that distinction in the interface.
- **FR-003**: System MUST NOT ask for information already present in state or derivable
  from information already present in state.
- **FR-004**: System MUST ask at most two questions per conversational turn.
- **FR-005**: Users MUST be able to revise any previously supplied answer at any point in
  the session.
- **FR-006**: System MUST invalidate exactly those downstream artifacts that depend on a
  revised slot, and MUST retain all others.
- **FR-007**: System MUST persist session state server side against a session identifier so
  that it survives both a page reload and a backend process restart.

**Marketplace**

- **FR-008**: System MUST provide a generated marketplace of at least two hundred and fifty
  listings spanning exactly ten categories, with at least ten distinct manufacturer brands
  present in every category.
- **FR-009**: The marketplace MUST contain both purchase and rental inventory sufficient
  for either flow to produce recommendations independently.
- **FR-010**: Purchase listings MUST carry the descriptive fields used in German vehicle
  trade, including first registration, mileage, power in kilowatts and metric horsepower,
  transmission, fuel, consumption, carbon dioxide emissions, emissions class, environmental
  badge, next inspection date, previous owner count, accident free status, price, tax
  deductibility, dealer and postal code.
- **FR-011**: Rental listings MUST additionally carry a four letter industry classification
  code, daily and weekly rates, minimum rental period, included kilometres, excess
  kilometre rate, deposit, and minimum driver age.
- **FR-012**: The marketplace MUST be produced by a seeded deterministic generator committed
  to the repository, and regeneration MUST reproduce the dataset byte for byte.
- **FR-013**: Generated attributes MUST be mutually coherent, such that price varies
  sensibly with age, mileage, power and equipment level within a model line.
- **FR-014**: All dealer, rental operator and marketplace names MUST be invented. No real
  dealership group, real rental company, or any BMW Group mark may appear.
- **FR-015**: System MUST expose marketplace search, single listing retrieval, and
  availability checking as callable tools.

**Ranking**

- **FR-016**: System MUST apply hard constraints as a deterministic boolean filter before
  any scoring occurs.
- **FR-017**: System MUST report the number of listings eliminated by each individual hard
  constraint.
- **FR-018**: System MUST score every surviving listing between zero and one hundred as a
  weighted sum over named dimensions covering price headroom, five year cost of ownership,
  age and mileage against segment norms, fit to the derived use case tags, condition
  signals, and dealer distance.
- **FR-019**: Scoring MUST be deterministic: identical state and dataset MUST yield
  identical scores and ordering.
- **FR-020**: Dimension weights MUST be derived from the interview, displayed to the user,
  and adjustable, and adjustment MUST re-rank the existing result set.
- **FR-021**: System MUST compute a five year cost of ownership for each recommendation
  comprising German motor vehicle tax, an estimated insurance band, expected fuel or energy
  cost at the user's annual mileage, estimated maintenance by segment and age, and an
  estimated residual value.
- **FR-022**: System MUST present for each recommendation a per dimension score breakdown,
  the dominant contributing factors, and an explicit quantified comparison against the next
  ranked alternative.
- **FR-023**: Explanatory prose MUST be generated from the score data, and every factual
  claim in it MUST correspond to a value present in that data.
- **FR-024**: The language model MUST NOT determine ordering or scores.

**Interactive surfaces**

- **FR-025**: The intake and booking form MUST be delivered as an application surface
  declared by the tool that opens it and rendered inside the conversation, not as a
  redirect or a separate page.
- **FR-026**: The form MUST present purchase fields or rental fields according to intent,
  validate before submission, and write submitted values into session state.
- **FR-027**: The checkout MUST be delivered as an application surface rendered inside the
  conversation.
- **FR-028**: The checkout MUST display an itemised order summary with value added tax at
  nineteen percent shown as a separate line.
- **FR-029**: The checkout MUST issue a purchase or rental contract confirmation carrying a
  generated reference, and for rentals MUST show collection location, collection window and
  deposit.
- **FR-030**: The checkout MUST carry a persistent simulation banner, a watermark on every
  generated document, and the token SIMULATION inside every contract and payment reference.
- **FR-031**: The checkout MUST use an obviously invalid bank identifier and MUST NOT
  contain any card number, expiry or security code input in any state.
- **FR-032**: The catalogue MUST be rendered as agent driven dynamic components defined
  against a registered component catalog, not as static markup.
- **FR-033**: A live progress surface MUST show slot filling with inferred values
  distinguished, the current phase, resolving filter counts, and streaming tool calls.
- **FR-034**: Both dynamic surfaces MUST update through incremental component and data model
  messages rather than wholesale replacement.

**Observability and evaluation**

- **FR-035**: System MUST emit a trace span for every agent turn, tool call and model
  completion, including the ranking tool's inputs and outputs.
- **FR-036**: System MUST provide at least twenty synthetic personas, each carrying a hidden
  ground truth need, and a harness that runs them programmatically.
- **FR-037**: The harness MUST report slot filling completeness, hard constraint violation
  count, rationale faithfulness, and turns to complete state.
- **FR-038**: Hard constraint violations MUST be detected deterministically rather than by
  model judgement.

**Delivery**

- **FR-039**: The system MUST start in full from a single container orchestration command.
- **FR-040**: Required environment variables MUST be documented with placeholder values, and
  no real credential may be committed.
- **FR-041**: The repository MUST document what the system does, how to run it, how ranking
  works, how to run the evaluations, and what the evaluations produced.
- **FR-042**: The system MUST run end to end on services that carry no billing
  relationship, so that a reviewer can start it without a payment method.
- **FR-043**: The model vendor and the payment vendor MUST each be selected by
  configuration and reached through a factory. No component outside the respective provider
  package may reference a vendor by name.
- **FR-044**: The system MUST degrade legibly when a model provider rate limit is reached,
  reporting that it is throttled rather than failing silently or presenting an empty result
  as an answer.

### Key Entities

- **Session**: a conversation identified by a session id, owning the interview state, the
  current phase, the active result set and any selection. Persisted server side.
- **InterviewState**: the typed slot structure covering intent, use case and derived tags,
  category preference, budget, target date and flexibility, hard constraints, soft
  preference weights and location. Each slot carries provenance, stated or inferred.
- **Listing**: a vehicle offered for purchase or rental, carrying descriptive, commercial
  and regulatory attributes, a category, a brand and model line, a dealer or operator, and a
  location.
- **RentalTerms**: the rental specific attributes attached to a rental listing, including
  the classification code, rates, included and excess kilometres, deposit, minimum period
  and minimum driver age.
- **FilterReport**: the outcome of the hard filter, holding the candidate count before and
  after and the elimination count attributed to each constraint.
- **ScoreBreakdown**: for one listing, the weight, raw dimension value and weighted
  contribution for every scoring dimension, plus the resulting total.
- **CostOfOwnership**: the five year projection for one listing, itemised into tax,
  insurance, energy, maintenance and residual value.
- **Recommendation**: a listing joined to its score breakdown, its cost of ownership, its
  rank, and its quantified comparison against the next alternative.
- **BookingDetails**: the values submitted through the intake form, differing by intent.
- **Order**: the simulated transaction, holding line items, net, tax and gross totals, the
  contract reference, the payment reference and, for rentals, collection terms and deposit.
- **Persona**: an evaluation fixture holding a scripted user, a hidden ground truth need,
  and the constraints its recommendations must satisfy.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Across the persona suite, zero recommendations violate a stated hard
  constraint.
- **SC-002**: The agent completes slot filling for at least ninety percent of personas
  within eight user turns.
- **SC-003**: Every slot required for ranking is populated before a ranking is produced, for
  one hundred percent of personas.
- **SC-004**: Re-running ranking on identical state and dataset reproduces the identical
  ordering and identical scores on one hundred percent of runs.
- **SC-005**: For every recommendation shown, the sum of weighted dimension contributions
  equals the displayed total score.
- **SC-006**: Rationale faithfulness, judged against the score breakdown, is at least
  ninety percent across the persona suite.
- **SC-007**: A user can move from first message to completed simulated checkout without
  leaving the conversation, in a single session.
- **SC-008**: Session state survives a page reload and a backend restart with no loss of
  filled slots.
- **SC-009**: The generated marketplace satisfies its scale floors: at least two hundred and
  fifty listings, exactly ten categories, at least ten brands in each category, verified by
  an automated check.
- **SC-010**: Regenerating the marketplace from the committed seed reproduces the committed
  dataset exactly.
- **SC-011**: No screen of the checkout flow lacks a visible simulation indicator, verified
  by an automated check over the rendered surface.
- **SC-012**: A reviewer can start the entire system with one command on a clean machine
  holding only an API key.

## Assumptions

- The marketplace is a generated fiction. No live listing source is contacted, and the
  system makes no claim to real inventory or real prices.
- Manufacturer names refer factually to real vehicles. All dealers, rental operators and
  marketplace branding are invented.
- The user is buying or renting in Germany. Prices are euro, taxes and regulatory fields
  follow German convention, and distances are kilometres.
- One user per session. There is no account system, no authentication, and no multi user
  authorisation model.
- Payment is simulated end to end. No payment processor, bank, or card network is contacted
  in any environment, including production.
- Vehicle imagery is placeholder. No manufacturer photography is used.
- Cost of ownership figures are transparent estimates from published formulas and segment
  averages, presented as estimates rather than quotations.
- The system runs on free service tiers. Those tiers impose request rate ceilings, so a
  multistep turn that issues several model calls can be throttled. The system is expected
  to surface throttling as a visible state rather than as a failure.
- The evaluation harness issues many model calls against a rate limited free tier, so it
  runs on demand rather than on every change, and may need to run in batches.
- The interface is German market facing with English glosses; full localisation is out of
  scope.
