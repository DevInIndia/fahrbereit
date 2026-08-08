# Handover

Written for a session with no memory of the one that produced this. Read it before
touching anything.

**Date**: 2026-08-08 · **Commits**: 36 · **Tests**: 234 passing, none require an API key
· **Branch**: `main`, clean, pushed to `github.com/DevInIndia/fahrbereit` (public)

---

## 1. Mandatory requirements, all ten

| | Requirement | State | Where |
|---|---|---|---|
| M-1 | Multistep agent on a permitted harness | **done** | `agent/session.py`, DeepAgents `create_deep_agent`, three tools in `agent/tools/interview.py` |
| M-2 | Form flow as an MCP App, rendered in chat | **done** | `mcpapps/formular/server.py`, `ui://formular/intake.html` |
| M-3 | Mock checkout as an MCP App, rendered in chat | **done** | `mcpapps/kasse/server.py`, `ui://kasse/checkout.html` |
| M-4 | Catalogue **and** live progress via A2UI | **done** | `agent/surfaces/katalog.py`, `agent/surfaces/fortschritt.py`, catalog in `ui/src/a2ui/` |
| M-5 | Payment fully mocked and visibly safe | **done** | `agent/payment/`, 24 safety tests in `tests/test_kasse.py` |
| M-6 | 250+ listings, 10 categories, 10+ brands each | **done** | `data/generate.py` seeded, 280 listings, `tests/test_dataset.py` |
| M-7 | State across interview, research, recommendation | **done, in memory** | `agent/state.py`, `agent/store.py`. Survives page reload, **not** a process restart |
| M-8 | Spec-driven development, artifacts committed | **done** | `specs/001-fahrbereit-agent/`, `.specify/memory/constitution.md` |
| M-9 | Ships as a Docker container | **done** | `docker-compose.yml`, four services, tested from a clean clone |
| M-10 | Public repo with a README that runs | **done** | `README.md`, quickstart written for a Docker beginner |

**Bonus B-1, observability**: done. `agent/observability.py`. Verified against the live
Langfuse project by reading a trace back from the API: 20 observations per turn, four
generations, four tool calls, plus a `fahrbereit.ranking` span carrying the filter
counts, weight vector and the winner's per dimension contributions (FR-035).

**Bonus B-2, persona evals**: **done.** `evals/run_evals.py` and `evals/personas.json`.
Eight personas (2 rentals). Zero hard constraint violations, 0.93 slot filling, 1.00 numerical
traceability, 1.00 judged faithfulness.

---

## 2. In progress

**Nothing.** The evaluation harness, bug fixes, and dataset linting are complete and committed.
The working tree is clean and the 234-test suite is green.

---

## 3. Three queued bugs (ALL FIXED)

All three deferred bugs have been resolved and verified:

### Bug 1: rental flow uses the ownership cost model (**FIXED in `8f78435`**)
Replaced ownership cost model with `rental_cost()` for `listing_type == "miete"`. Costs base price over days, fuel over distance, and excess km, reporting deposit separately. `cost_of_ownership()` raises `ValueError` on rentals.

### Bug 2: pickup distance is a soft weight for rentals (**FIXED in `cb3e824`**)
Added a default 100 km pickup radius for rentals in `agent/tools/ranking.py`.
*Correction Note*: The earlier handover description overstated the work required. The hard constraint already existed in `CONSTRAINT_ORDER`, `_fails`, drop counts, and `i18n`; the only missing element was supplying a default radius for rental paths.

### Bug 3: remaining raw display strings (**FIXED in `e8675da`**)
Corrected spelling of Škoda in `data/vocab.py` and regenerated `data/listings.json` deterministically. Added automated tree-walking lint tests for raw display strings and slot labels.

---

## 4. Decisions already made. Do not relitigate.

These were each decided deliberately, some after being challenged. Reopening them costs
time and changes nothing.

- **German market framing stays.** German trade vocabulary, German regulatory fields,
  euro, kilometres. This is not a placeholder.
- **The marketplace is a generated mock and stays one.** 280 listings from a seeded
  generator. The brief explicitly permits this. No scraping, no listing API. Rationale
  and rejected alternatives are in `specs/001-fahrbereit-agent/research.md`.
- **No real marketplace integration** was attempted. If it is ever added, the mock stays
  as the fallback and the interface must say plainly which is in use. Everything
  downstream reads the typed `Listing` model, so the swap point is the loader in
  `agent/listing.py` and nothing else.
- **Path 2 for MCP Apps.** We host the app bridge ourselves in React, hold our own MCP
  client, fetch the `ui://` resource and render the sandboxed iframe.
  `@ag-ui/mcp-apps-middleware` 0.0.3 injected zero tools in the spike and the cause was
  never established; that is recorded as unresolved in `docs/spike-notes.md`, not as a
  claim the package is broken. Do not spend time on the middleware again.
- **DeepAgents on Gemini free tier.** The Claude Agent SDK was dropped under a zero cost
  constraint: Anthropic sells prepaid credits with no free tier, and subscription OAuth is
  barred for third party use by policy. The decision record with rejected alternatives is
  in `specs/001-fahrbereit-agent/research.md`. The superseded choice is kept in the log on purpose.
- **Loud fallback behaviour.** When the MCP path degrades, `/api/health` reports
  `remote-degraded` and the last error. Silent fallbacks were the single most expensive
  class of bug in this build: they look exactly like success. Keep every fallback loud.
- **First card open, rest collapsed** in the catalogue. Confirmed as correct.
- **English is the default language**, German still available and the choice persists.
- **Ranking constants are invented and labelled as such.** The claim made in the README
  and the code is determinism, checkable arithmetic and adjustable weights, **not** that
  the weights are correct. Do not upgrade that claim. Audit in `specs/001-fahrbereit-agent/research.md`.

---

## 5. Live constraints, learned the hard way

- **Quota: 500 requests per day** on `gemini-3.5-flash-lite`, 15 per minute. A turn costs
  three to four calls, so roughly 125 turns a day. The full Flash models are 20 per day
  and unusable. Verified figures are in `specs/001-fahrbereit-agent/research.md`.
- **Set `MODEL_CACHE=1` during development.** Repeating a test conversation then costs
  nothing. Turn it off for a demonstration: a cached answer to a question that was not
  asked is worse than a slow one.
- **Run uvicorn with `--reload`**, or use `python run_backend.py`. Twice in this build a
  fix appeared not to work because a stale server was still answering.
- **Killing a stray server on :8000: use PowerShell `Stop-Process -Force`, not
  `taskkill`.** `taskkill` reported success while the process survived and kept serving
  old code. Two servers were bound to the port at once and the stale one answered.
  ```powershell
  Get-Process python* | Stop-Process -Force
  ```
- **Gemma is not usable on any interactive path.** 16 times slower than the reasoning
  model, and its thinking blocks cannot be disabled. Use it only for offline or bulk work,
  where its 14,400 per day is genuinely valuable, for example eval judging.
- **The A2UI wire format is v0.9**, `createSurface` and `updateComponents` with flat
  props. The renderer accepts v0.8 messages silently and draws nothing.
- **Vite is pinned to 7.** Vite 8 could not load its rolldown native binding on Windows.
- **`zod` is pinned to 3**, matching the A2UI renderer. Version 4 fails to typecheck.
- **Our package is `mcpapps/`, not `mcp/`**, because a top level `mcp` shadows the SDK.

---

## 6. What remains

**Required for submission:**

1. **Slide deck.** Template from the organisers. Structure: problem, architecture, protocol implementations, ranking pipeline with worked example, eval results, demo link.
2. **Video demo**, two to four minutes, scripted. Must show: inference confirmation, live progress surface, ranked catalogue, "Warum dieses Auto" panel, chat form, checkout with SIMULATION banner, state persistence reload.

**Completed in full:**

- Persona evals (B-2): Done in `evals/`.
- Three queued bugs: Done (`8f78435`, `cb3e824`, `e8675da`).
- README final pass with traceability table, disclosures, worked ranking example, and known limitations: Done.

---

## 7. Fastest way to see it working

```bash
docker compose up --build
```

Open `http://localhost:8080`. Needs `.env` with `GOOGLE_API_KEY`; copy `.env.example`.

Without Docker, two terminals:

```bash
.venv/Scripts/python.exe run_backend.py
```

```bash
cd ui && npm run dev
```

Then `http://localhost:5173`.

The ranking engine alone, no model and no interface:

```bash
.venv/Scripts/python.exe -m scripts.demo_ranking
```

The whole suite, no API key and no network:

```bash
.venv/Scripts/python.exe -m pytest tests/ -q
```

The persona buttons in the left column bypass the model entirely. They are the
fallback if the quota runs out mid demonstration.
