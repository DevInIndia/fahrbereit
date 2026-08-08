# Video Demonstration Script: fahrbereit

Scripted 2 to 4 minute video demonstration walkthrough for hackathon submission.

---

## Video Plan & Setup

* **Target Duration**: ~3 minutes
* **Target Audience**: Hackathon judges and software reviewers
* **Environment Setup**: `docker compose up --build` running locally on `http://localhost:8080`.

---

## Timeline & Narration Script

### 0:00 - 0:30 | Introduction & Architecture Core Claim
* **Visual**: Screen opens on `http://localhost:8080`. Two-column dark layout with English/German toggle on top left, persona buttons, interview panel on left, chat and catalogue on right.
* **Narration**: 
  > "Welcome to fahrbereit, an AI conversational car matchmaker for buying and renting cars in Germany. The core principle of our architecture is that the language model is never allowed to compute user-facing numbers. All filtering, percentile scoring, German vehicle tax calculations, and cost-of-ownership math are executed in pure, deterministic Python before the agent speaks. The language model reads and narrates checkable arithmetic."

### 0:30 - 1:00 | Instant Persona Shortcut (No Model / No Quota)
* **Visual**: Click the **Familie** persona button on the left sidebar. The catalogue below populates instantly within 1 second. Click the first vehicle card to expand its score breakdown.
* **Narration**: 
  > "On the left sidebar, our persona buttons bypass the language model entirely to demonstrate our deterministic ranking engine instantly without consuming API quota. Clicking 'Familie' filters 280 listings across 10 categories, ranks candidates across six weighted dimensions, and displays the exact score contributions for the winning Kia Carnival."

### 1:00 - 1:45 | Conversational Turn & Live A2UI Progress Surface
* **Visual**: Type into the chat box: *"Ich brauche für ein Wochenende ein Auto für einen Umzug in Hamburg, Budget 95 Euro am Tag."* Click **Send**. Point cursor at the live progress surface streaming incremental thoughts and tool calls via A2UI SSE.
* **Narration**: 
  > "Now let's test a live conversational turn. I type a rental request in German for a moving flat weekend in Hamburg. Watch the live progress panel powered by A2UI SSE streaming. The agent calls our `interview` tool to record slots with explicit provenance—marking stated constraints, inferred parameters, and default assumptions. Provenance is visually distinct: solid tags for stated items, dashed tags for assumed defaults."

### 1:45 - 2:15 | Ranked Catalogue & "Warum dieses Auto" Rationale
* **Visual**: Scroll down to the updated A2UI catalogue. Hover over the "Warum dieses Auto" panel explaining why the Kia Carnival beat the Seat Leon runner-up.
* **Narration**: 
  > "The ranked catalogue updates dynamically. Notice our dedicated rental cost model: for a 3-day rental, it costs base rates over days, fuel over distance, and excess mileage penalties, while keeping refundable deposits separate. Notice also our pickup radius constraint—automatically capping rental pickup distance at 100 km."

### 2:15 - 2:45 | MCP Apps: Form Filling & Simulated Checkout
* **Visual**: Click **Formular** in the flow controls. An intake form renders directly inside the chat window inside a sandboxed iframe (`ui://formular/intake.html`). Fill name and submit. Then click **Kasse** to show the checkout MCP App (`ui://kasse/checkout.html`) displaying net, 19% VAT, gross total, and the orange `SIMULATION` banner across the top.
* **Narration**: 
  > "Booking and purchase confirmation happen without leaving the chat stream using MCP Apps. Here, the intake form and checkout interface render as sandboxed iframes driven by protocol resources. Payment is 100% simulated end-to-end—no card input fields exist in the entire codebase, and a prominent orange SIMULATION banner is displayed."

### 2:45 - 3:00 | Reload & Persistence Verification
* **Visual**: Refresh the browser page (`F5`). State persists cleanly and the interview panel reloads existing slot history.
* **Narration**: 
  > "Finally, refreshing the browser demonstrates state persistence across the interview and recommendation steps. Thank you for watching!"
