# Context Handover & Rollback Log

This document provides a comprehensive handover record and rollback log for future Claude / AI agent coding sessions.

---

## 1. Environment & Repository Snapshot

* **Date**: 2026-08-08
* **Branch**: `main` (working tree clean)
* **HEAD Commit**: `98c426e1787f1e13c6f5f96f6bc0ae8f471af738`
* **Test Suite**: 234 passing tests (`.venv/Scripts/python.exe -m pytest tests/ -q`), 0 failures, 0 network dependencies.
* **Python Path**: `.venv/Scripts/python.exe`
* **Backend Entry Point**: `run_backend.py`
* **Frontend Entry Point**: `cd ui && npm run dev`
* **Docker Setup**: `docker compose up --build` (4 services: `ui`, `backend`, `formular`, `kasse`).

---

## 2. Rollback Commands & Safety Guidelines

If you need to check state, undo changes, or roll back to a known working commit, use the following PowerShell commands:

### Check Current Status and History
```powershell
# Check current working tree state
git status

# View recent 10 commits with hashes
git log -n 10 --oneline

# View diff of unstaged changes
git diff

# View diff of staged changes
git diff --cached
```

### Undo / Rollback Operations
```powershell
# Revert uncommitted changes in a specific file
git checkout HEAD -- path/to/file

# Revert ALL uncommitted changes in the repository
git checkout HEAD -- .

# Reset working directory and index cleanly to current HEAD (98c426e)
git reset --hard 98c426e1787f1e13c6f5f96f6bc0ae8f471af738

# Roll back to the commit before persona evals (commit e8675da)
git reset --hard e8675da394d9e1eb2bc5bf439de843b22bd89933

# Create a safe revert commit for a specific committed change
git revert <commit-hash>
```

### Process Management Safety
```powershell
# Kill stray python/uvicorn servers holding port 8000 (DO NOT use taskkill)
Get-Process python* | Stop-Process -Force
```

---

## 3. Recent Commit Audit (Last 4 Commits)

### Commit `98c426e` - `feat(evals): persona evaluation harness, eight personas`
* **Scope**: Implemented Bonus B-2 persona evaluation framework.
* **Files**: [evals/personas.json](file:///c:/Users/lenovo/Documents/GitHub/fahrbereit/evals/personas.json), [evals/scoring.py](file:///c:/Users/lenovo/Documents/GitHub/fahrbereit/evals/scoring.py), [evals/judge.py](file:///c:/Users/lenovo/Documents/GitHub/fahrbereit/evals/judge.py), [evals/run_evals.py](file:///c:/Users/lenovo/Documents/GitHub/fahrbereit/evals/run_evals.py).
* **Details**: 8 personas (2 rentals). Deterministic checks for hard constraints and figure traceability; Gemma 4 31B LLM judge for rationale quality. 
* **Note on Committed `evals/results.json`**: The committed file predates a scoring fix for digits in model names (e.g., Fiat 500, Mercedes C 200) and user boot requirements. The extractor in [evals/scoring.py](file:///c:/Users/lenovo/Documents/GitHub/fahrbereit/evals/scoring.py) now permits these; re-running evals (`MODEL_CACHE=0 .venv/Scripts/python.exe -m evals.run_evals`) updates results cleanly.

### Commit `e8675da` - `fix(data): spell Škoda correctly, and pin the no-raw-identifiers rule`
* **Scope**: Fixed brand spelling in [vocab.py](file:///c:/Users/lenovo/Documents/GitHub/fahrbereit/data/vocab.py) and regenerated [listings.json](file:///c:/Users/lenovo/Documents/GitHub/fahrbereit/data/listings.json) deterministically.
* **Details**: Verified deterministic generation byte-for-byte. Added raw identifier lint tests and missing slot label tests (Tests 227-234).

### Commit `cb3e824` - `fix(ranking): give rentals a default pickup radius`
* **Scope**: Default 100 km pickup radius constraint for rental paths.
* **Details**: Added default rental pickup radius in [ranking.py](file:///c:/Users/lenovo/Documents/GitHub/fahrbereit/agent/tools/ranking.py) and reported in `FilterReport`. Prevents Hamburg renters from receiving 400 km distant van recommendations.

### Commit `8f78435` - `fix(tco): cost rentals as rentals, not as five years of ownership`
* **Scope**: Dedicated rental cost model `rental_cost()`.
* **Details**: Base price over days + fuel + excess km; deposit reported separately. `cost_of_ownership()` raises `ValueError` on rentals. Added `mietdauer_tage` state slot.

---

## 4. Current Work Status & Queued Tasks

The implementation plan is currently **ON HOLD** per user request. When resumed, the prioritized tasks are:

1. **Task 1: Live Evals Re-run**
   * Run `MODEL_CACHE=0 .venv/Scripts/python.exe -m evals.run_evals` to publish updated, false-positive-free evaluation metrics in [evals/results.json](file:///c:/Users/lenovo/Documents/GitHub/fahrbereit/evals/results.json).

2. **Task 2: Seeded Data Disclosures**
   * UI header in [App.tsx](file:///c:/Users/lenovo/Documents/GitHub/fahrbereit/ui/src/App.tsx).
   * Notice line in [README.md](file:///c:/Users/lenovo/Documents/GitHub/fahrbereit/README.md).
   * Listing loader swap note in [specs/001-fahrbereit-agent/research.md](file:///c:/Users/lenovo/Documents/GitHub/fahrbereit/specs/001-fahrbereit-agent/research.md).

3. **Task 3: README Final Pass**
   * Insert Requirements Traceability Table (M-1 to M-10 + B-1, B-2).
   * Insert worked ranking calculation example from [demo_ranking.py](file:///c:/Users/lenovo/Documents/GitHub/fahrbereit/scripts/demo_ranking.py).
   * Document honest known limitations (`RESTWERT_RATE`, electricity price 0.39 EUR/kWh, rental/purchase mix in `UNENTSCHIEDEN`, in-memory store restart behavior, custom MCP bridge).
   * Update status section.

4. **Task 4: Document Reconciliation**
   * Reconcile [docs/state.md](file:///c:/Users/lenovo/Documents/GitHub/fahrbereit/docs/state.md) and [specs/001-fahrbereit-agent/tasks.md](file:///c:/Users/lenovo/Documents/GitHub/fahrbereit/specs/001-fahrbereit-agent/tasks.md) to mark fixed bugs and completed B-2 evals.

5. **Task 5: Deliverables & Architecture**
   * Author [docs/architecture.md](file:///c:/Users/lenovo/Documents/GitHub/fahrbereit/docs/architecture.md).
   * Create slide deck outline and video demo script.

---

## 5. Standing Rules & Principles

- **Number Calculations**: Model narrates numbers; Python computes them. Never allow the model to produce user-facing numbers.
- **Mock Boundary**: Payment is fully mocked (`agent/payment/mock.py`). Listings are synthetic 280 items (`data/listings.json`).
- **Formatting Constraints**: No em dashes anywhere in code, comments, docs, or logs. No emojis anywhere.
- **Language**: English default in UI, German trade vocabulary in domain model. Persistent toggle.
