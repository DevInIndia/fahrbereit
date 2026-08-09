# Slide Deck Structure: fahrbereit

Recommended presentation deck outline for hackathon submission (Amulate Summer Hackathon 2026).

---

## Slide 1: Title & Core Claim
* **Title**: fahrbereit - AI Conversational Car Matchmaker for Buying and Renting in Germany
* **Subtitle**: Multistep reasoning agent with A2UI Generative UI, MCP Apps, and 100% deterministic ranking arithmetic.
* **Key Claim**: *The model never computes numbers.* Scoring, German vehicle taxes, and TCO are computed in pure Python before anything is said. The model narrates checkable arithmetic.

---

## Slide 2: The Problem & German Market Context
* **Problem**: Buying or renting a car in Germany requires navigating trade vocabulary (e.g. Kfz-Steuer, Umweltplakette, HU/AU, Kaution), complex tax formulas, and misleading list prices.
* **Our Solution**: An interactive agent that asks at most two follow-up questions, infers situation parameters with clear provenance (Stated vs Inferred vs Assumed), filters 280 listings deterministically, and presents ranked, explained options.

---

## Slide 3: System Architecture
* **Container Architecture**: 4 isolated Docker services (`ui`, `backend`, `formular`, `kasse`).
* **Agent Harness**: LangChain DeepAgents (`create_deep_agent`) with LangGraph `InMemorySaver` checkpointer.
* **Model Routing**: Gemini 3.5 Flash Lite for fast interactive turns; Gemma 4 31B for bulk evaluation judging.

---

## Slide 4: Protocol Implementations (MCP Apps & A2UI)
* **MCP Apps**: Sandboxed intake form (`ui://formular/intake.html`) and simulated checkout (`ui://kasse/checkout.html`) rendered directly inside the conversation stream.
* **A2UI Generative UI**: Streaming catalogue cards and live agent progress surface over SSE (v0.9 protocol format).
* **Mock Payment Security**: 100% simulated checkout with visible `SIMULATION` watermark; zero credit card input fields.

---

## Slide 5: Deterministic Ranking & TCO Engine
* **2-Stage Pipeline**: 
  1. Boolean hard filter (type, budget, trunk, seats, 100 km rental pickup radius).
  2. Weighted percentile scoring over 6 transparent dimensions.
* **Exact Cost Formulas**: German 5-year TCO including Kfz-Steuer emissions tax formula and EV exemptions through 2030; dedicated `rental_cost()` model for hires.
* **Worked Example**: Show step-by-step arithmetic from `scripts/demo_ranking.py`.

---

## Slide 6: Observability & Persona Evaluation Results
* **Langfuse Tracing (Bonus B-1)**: Full OpenTelemetry tracing capturing LLM generations, tool execution, and custom `fahrbereit.ranking` spans.
* **Evaluation Harness (Bonus B-2)**: Tested across 8 personas (6 purchase, 2 rental):
  * Hard Constraint Violations: **0**
  * Slot Filling Mean: **0.93**
  * Numerical Traceability Ratio: **1.00** (100% of emitted figures trace back to Python data)
  * Judged Rationale Faithfulness: **1.00**

---

## Slide 7: Demonstration & Repository Links
* **Live Demo**: Open `http://localhost:8080` (or run `docker compose up --build`).
* **Persona Shortcuts**: Instant fallback buttons bypassing the LLM for quota-free evaluation.
* **GitHub Repository**: `github.com/DevInIndia/fahrbereit` (Public, 266 passing tests).
