# Architecture Specification: fahrbereit

System architecture for **fahrbereit**, a conversational car recommendation agent for German purchase and rental markets.

---

## 1. System Overview & Container Topology

The application is deployed as four isolated Docker services communicating over an internal Docker bridge network (`fahrbereit-net`). The browser communicates solely with the `ui` service on port 8080.

```
                     Browser Client
                           |
                 http://localhost:8080
                           |
              +------------v------------+
              |           ui            |   nginx 1.27
              |      (Port 8080)        |   Serves React bundle & proxies /api
              +------------+------------+
                           | /api
              +------------v------------+
              |         backend         |   FastAPI + Uvicorn (Port 8000)
              |       DeepAgents        |   Interview state, ranking engine,
              +----+---------------+----+   A2UI surfaces & MCP client
                   |               |
       Model Context Protocol (HTTP/JSON-RPC)
                   |               |
        +----------v---+       +---v----------+
        |   formular   |       |    kasse     |   MCP App Servers
        |  (Port 3001) |       | (Port 3002)  |   (FastAPI / Python MCP SDK)
        +--------------+       +--------------+
```

### Container Responsibilities
* **`ui`**: Nginx web server serving the static React (Vite 7) single-page application. Handles reverse proxying of `/api/*` routes to `backend:8000`.
* **`backend`**: Python FastAPI backend hosting the LangChain DeepAgents session orchestrator, the typed `InterviewState` record, the deterministic Python ranking & TCO engines, and the A2UI surface generators.
* **`formular`**: Standalone MCP server managing the user intake form resource (`ui://formular/intake.html`).
* **`kasse`**: Standalone MCP server managing the simulated checkout resource (`ui://kasse/checkout.html`).

---

## 2. Core Architecture Claim & Control Flow

The core architecture claim of **fahrbereit** is strict separation of reasoning and arithmetic:

> **The Language Model never computes user-facing figures.** Filtering, weighted percentile scoring, vehicle taxation (Kfz-Steuer), and 5-year cost of ownership (TCO) / rental pricing are computed in pure Python before any text is generated. The model reads these pre-computed numbers and narrates them.

```
 User Input
     |
     v
+------------------------+
| LangChain DeepAgents   |  <---> LangGraph InMemorySaver Checkpointer
| Session Orchestrator   |
+--------+---------------+
         |
         | (Tool Call: record_slots, rank_listings, cost_of_ownership)
         v
+------------------------+
| Deterministic Python   |  1. Hard Filtering (Type, Budget, Trunk, Radius)
| Ranking & TCO Engine   |  2. Weighted Percentile Scoring (6 Dimensions)
+--------+---------------+  3. TCO Arithmetic (Kfz-Steuer, Depreciation, Fuel)
         |
         v
  Exact Numerical Results
         |
         v
+------------------------+
| Model Narration &      |  Reads pre-computed numbers; strictly prohibited from
| A2UI Surface Output    |  inventing fallback figures.
+------------------------+
```

---

## 3. Dynamic UI Protocol (A2UI v0.9)

UI updates are streamed using Google's Agent-to-UI (A2UI v0.9) wire protocol over Server-Sent Events (SSE).

* **Wire Messages**: Uses `createSurface` and `updateComponents` with flat component properties.
* **Catalogue Surface** (`fahrbereit-katalog`): Renders ranked vehicle cards, expandable score breakdowns, and dimension contribution bars. First card defaults to open.
* **Progress Surface** (`fahrbereit-fortschritt`): Streams incremental agent thought steps, active tool calls, and state inferences directly into the UI panel as they occur.

---

## 4. Model Context Protocol (MCP) Apps Integration

Form-filling and checkout interactions are implemented as MCP Apps rendered directly inside the chat stream.

* **Path 2 Architecture**: The React client acts as the MCP host (`@modelcontextprotocol/ext-apps`), holding direct connections to the MCP servers, fetching `ui://` resources, and embedding them in sandboxed `<iframe>` containers.
* **Intake Form App** (`mcpapps/formular/`): Captures structured customer details and returns confirmation events to the conversation.
* **Checkout Simulation App** (`mcpapps/kasse/`): Renders simulated invoice line items (net, 19% VAT, gross total) with a prominent orange `SIMULATION` banner.
* **Mock Payment Security**: Payment is 100% simulated (`agent/payment/mock.py`). No credit card inputs or bank endpoints exist anywhere in the repository (enforced by automated AST scan tests).

---

## 5. Ranking Engine & Cost Models

### Deterministic Filtering & Percentile Scoring
1. **Hard Constraints Filter**: Filters candidate listings by intent (`kauf` vs `miete`), budget ceiling, seating capacity, trunk volume, fuel type, transmission, green emissions badge, and default pickup radius (100 km for rentals).
2. **Weighted Percentile Scoring**: Scores surviving listings across six dimensions:
   - `preis_spielraum` (Price vs budget headroom)
   - `einsatzzweck` (Use-case alignment & cargo capacity)
   - `gesamtkosten` (5-year TCO for purchases / 3-day rental total for rentals)
   - `alter_laufleistung` (Age & mileage penalty)
   - `zustand` (Accident history, previous owners, inspection months)
   - `entfernung` (Geographic distance from user postal code)

### TCO & Rental Cost Formulas
* **Purchase TCO** (`cost_of_ownership`): Sums 5-year depreciation (`RESTWERT_RATE`), annual Kfz-Steuer tax (incorporating engine displacement, CO2 emissions, and electric exemptions to 31.12.2030), estimated fuel at 0.39 EUR/kWh electric or market fuel rates, maintenance, and insurance.
* **Rental Cost** (`rental_cost`): Calculates duration-based rates (weekly rate applied if cheaper than daily), fuel over distance, excess mileage penalties above included allowances, and separate refundable deposit reporting. Raises `ValueError` if invoked on purchase listings.

---

## 6. Observability & Evaluation

* **Observability (Bonus B-1)**: OpenTelemetry integration streaming to Langfuse. Captures ~20 observations per conversation turn, including LLM generations, tool execution latencies, and custom `fahrbereit.ranking` spans carrying filter drop counts and dimension weights.
* **Persona Evaluation Harness (Bonus B-2)**: 8 test personas (6 purchases, 2 rentals) in `evals/personas.json`. Measures hard constraint compliance (100% deterministic), slot filling completeness, numerical traceability (1.00 ratio), and rationale quality using Gemma 4 31B as an LLM judge.
