# Context Handover & Rollback Log

This document provides a comprehensive handover record and rollback log for future Claude / AI agent coding sessions.

---

## 1. Environment & Repository Snapshot

* **Date**: 2026-08-08
* **Branch**: `main` (working tree clean)
* **HEAD Commit**: `a4c1c5f` (`docs: add architecture specification, slide deck outline, and video demo script`)
* **Test Suite**: 236 passing tests (`.venv/Scripts/python.exe -m pytest tests/ -q`), 0 failures, 0 network dependencies.
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

# Reset working directory and index cleanly to commit before Live Market Check
git reset --hard a4c1c5f

# Create a safe revert commit for a specific committed change
git revert <commit-hash>
```

### Process Management Safety
```powershell
# Kill stray python/uvicorn servers holding port 8000 (DO NOT use taskkill)
Get-Process python* | Stop-Process -Force
```

---

## 3. Live Market Check (Gemini Search Grounding) Verification & Architecture

* **Quota Verification**: Tested Gemini API models with search grounding tool (`google_search=GoogleSearch()`). Free-tier Google AI Studio API keys return `429 RESOURCE_EXHAUSTED` (limit: 0 requests/day for grounded search tools on free tier). Plain model generation (`gemini-3.5-flash-lite`, `gemma-4-31b-it`) functions normally.
* **Modular Seam Design**: Implemented `agent/model/live_check.py` (respecting `test_no_vendor_import_outside_the_model_package`) and exposed via thin bridge `agent/live_check.py` and `POST /api/live-market-check` in `agent/server.py`.
* **UI Isolation**: Single optional button on top-ranked card only (`rang === 1`) in `ui/src/a2ui/catalog.tsx`. Fails gracefully displaying `"Live check unavailable"` badge on quota errors. Display-only validation that never touches ranking math.

---

## 4. Standing Rules & Principles

- **Number Calculations**: Model narrates numbers; Python computes them. Never allow the model to produce user-facing numbers.
- **Mock Boundary**: Payment is fully mocked (`agent/payment/mock.py`). Listings are synthetic 280 items (`data/listings.json`).
- **Formatting Constraints**: No em dashes anywhere in code, comments, docs, or logs. No emojis anywhere.
- **Language**: English default in UI, German trade vocabulary in domain model. Persistent toggle.
