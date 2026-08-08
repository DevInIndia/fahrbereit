# Context Handover & Rollback Log

This document provides a comprehensive handover record and rollback log for future Claude / AI agent coding sessions.

---

## 1. Environment & Repository Snapshot

* **Date**: 2026-08-08
* **Branch**: `main` (working tree clean)
* **HEAD Commit**: `0f0b450` (`docs(readme): final pass with requirement traceability, disclosures, and state reconciliation`)
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

# Reset working directory and index cleanly to current HEAD (0f0b450)
git reset --hard 0f0b450

# Roll back to the commit before documentation final pass (commit 396fad5)
git reset --hard 396fad5

# Roll back to the commit before live evals commit (commit 5deb830)
git reset --hard 5deb830

# Create a safe revert commit for a specific committed change
git revert <commit-hash>
```

### Process Management Safety
```powershell
# Kill stray python/uvicorn servers holding port 8000 (DO NOT use taskkill)
Get-Process python* | Stop-Process -Force
```

---

## 3. Recent Commit Audit (Latest Commits)

### Commit `0f0b450` - `docs(readme): final pass with requirement traceability, disclosures, and state reconciliation`
* **Scope**: Documentation, synthetic dataset disclosures, and state reconciliation.
* **Files**: [README.md](file:///c:/Users/lenovo/Documents/GitHub/fahrbereit/README.md), [docs/state.md](file:///c:/Users/lenovo/Documents/GitHub/fahrbereit/docs/state.md), [specs/001-fahrbereit-agent/tasks.md](file:///c:/Users/lenovo/Documents/GitHub/fahrbereit/specs/001-fahrbereit-agent/tasks.md), [specs/001-fahrbereit-agent/research.md](file:///c:/Users/lenovo/Documents/GitHub/fahrbereit/specs/001-fahrbereit-agent/research.md), [ui/src/App.tsx](file:///c:/Users/lenovo/Documents/GitHub/fahrbereit/ui/src/App.tsx), [ui/src/i18n.ts](file:///c:/Users/lenovo/Documents/GitHub/fahrbereit/ui/src/i18n.ts).
* **Details**: Added Requirements Traceability Table (M-1 to M-10 + B-1/B-2), worked ranking example from `scripts/demo_ranking.py`, honest known limitations (`RESTWERT_RATE`, electricity price 0.39 EUR/kWh, unit sorting under `UNENTSCHIEDEN`, in-memory store restart behavior, custom MCP bridge), synthetic data disclosures across UI/README/research.md, and reconciled `docs/state.md` and `tasks.md` noting Bug 2 description overstatement.

### Commit `396fad5` - `feat(evals): commit live persona evaluation results with 1.00 numerical traceability`
* **Scope**: Published live 8-persona evaluation results (`MODEL_CACHE=0`).
* **Files**: [evals/results.json](file:///c:/Users/lenovo/Documents/GitHub/fahrbereit/evals/results.json).
* **Details**: 64 model calls across 8 personas. Hard constraint violations: 0, slot filling mean: 0.93, numerical traceability: 1.00 (100% of emitted numbers trace back to Python data, confirming false positives like Fiat 500/Mercedes C 200/550 L boot capacity are gone), judged faithfulness: 1.00.

### Commit `5deb830` - `fix(ranking): loosen umzug persona hard boot constraint to eliminate double-counting`
* **Scope**: Persona constraint modeling fix.
* **Files**: [agent/server.py](file:///c:/Users/lenovo/Documents/GitHub/fahrbereit/agent/server.py), [scripts/demo_ranking.py](file:///c:/Users/lenovo/Documents/GitHub/fahrbereit/scripts/demo_ranking.py).
* **Details**: Changed `min_kofferraum_liter` from 550 to 350 liters in the `umzug` demo persona definitions to eliminate double-counting between the hard cutoff and soft `Ladevolumen` weighting. `demo_ranking.py --persona umzug` now returns 3 candidates with Kia Carnival (698 L boot) winning on cargo merit.

---

## 4. Current Work Status & Deliverables

All building tasks are **COMPLETE** and verified:
1. **Mandatory Requirements (M-1 to M-10)**: All 10 built and verified.
2. **Bonus Requirements**: B-1 (Langfuse observability) and B-2 (Persona evals) completed.
3. **Documentation Assets Created**:
   * [docs/architecture.md](file:///c:/Users/lenovo/Documents/GitHub/fahrbereit/docs/architecture.md): Container topology, DeepAgents orchestrator, A2UI v0.9 streaming, MCP App bridge, ranking/TCO formulas, and Langfuse tracing.
   * [docs/slide_deck_outline.md](file:///c:/Users/lenovo/Documents/GitHub/fahrbereit/docs/slide_deck_outline.md): Presentation deck structure for submission.
   * [docs/video_demo_script.md](file:///c:/Users/lenovo/Documents/GitHub/fahrbereit/docs/video_demo_script.md): Scripted 3-minute video walkthrough.

---

## 5. Standing Rules & Principles

- **Number Calculations**: Model narrates numbers; Python computes them. Never allow the model to produce user-facing numbers.
- **Mock Boundary**: Payment is fully mocked (`agent/payment/mock.py`). Listings are synthetic 280 items (`data/listings.json`).
- **Formatting Constraints**: No em dashes anywhere in code, comments, docs, or logs. No emojis anywhere.
- **Language**: English default in UI, German trade vocabulary in domain model. Persistent toggle.
