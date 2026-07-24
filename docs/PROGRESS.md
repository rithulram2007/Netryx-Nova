# PROGRESS — Session State & Dynamic Memory Log

## Current Status

| Aspect | Status |
|---|---|
| Pre-refactor codebase | Fully functional Tkinter monolith (test_super.py, 2794 lines) |
| Documentation templates | Created, then **architecturally reviewed** |
| Review findings | 24 issues identified: 5 inconsistencies, 5 contradictions, 7 missing decisions, 7 improvements |
| Fixes applied | ASYNC execution model, Leaflet-only, `core/pipeline.py`, `utils/tile_downloader.py`, VRAM mgmt, Optional PCA, 2-tier candidates, corrected dependency graph, ADR-002 + ADR-003 |
| Refactoring | Phase 1 complete — netryx_loader, retrieval, tile_downloader, geo_utils, test fixtures |
| Blockers | None identified yet |

## What Exists (Pre-Refactor)

- **Full 3-stage pipeline** working in test_super.py (lines 1848-2036)
- **MegaLoc model** loading with MPS patches in megaloc_utils.py (350 lines)
- **Self-contained MegaLoc PyTorch model** in megaloc_model.py (277 lines)
- **MASt3R dense matcher** integration in mast3r_utils.py (163 lines)
- **Community Hub** upload/download/export/import in netryx_hub.py (771 lines) — Hugging Face backed
- **MixVPR encoder** (optional) in mixvpr_utils.py (179 lines) — to be removed in refactor
- **Compact index** builder with PCA fitting in test_super.py (lines 493-738)
- **Custom Tkinter widgets** (RoundedButton, RoundedEntry, RoundedRadio) — to be removed
- **Spatial consensus** algorithm inline in test_super.py (lines 1988-2024)

## Session Log

### Session 1 — 2026-07-24
- Audited full existing codebase
- Defined modular target architecture based on PRD
- Created context documentation system (AGENTS.md, CODING_STANDARDS.md, PROJECT_OVERVIEW.md, GIT_STANDARDS.md)
- Created docs/ directory structure with ROADMAP.md, PROGRESS.md
- Created architecture, decision record, API spec, feature task docs
- **Next**: Begin Phase 0 — set up pyproject.toml, config.py, directory structure

### Session 2 — 2026-07-24 (Architectural Review)
- Read all 17 documentation files
- Identified 24 architectural issues across 6 categories
- Applied structural fixes: async model, Leaflet-only, 2-tier candidates, VRAM mgmt, Optional PCA, etc.
- Created ADR-002 (Pipeline Controller), ADR-003 (Frontend Architecture)
- **Next**: Begin Phase 0 implementation

### Session 3 — 2026-07-24 (Phase 0: Skeleton)
- Created directory structure: `core/`, `engines/`, `utils/`, `ui/`, `modal_app/`, `tests/`, `scripts/`
- Created `pyproject.toml` with ruff, mypy, pytest config
- Created `config.py` extracting all thresholds from test_super.py
- Created `core/exceptions.py` with 7 custom exception classes
- Created `app.py` FastAPI entrypoint with CORS, health endpoint
- Verified with ruff + mypy (zero errors)
- **Next**: Phase 1 — Data Layer

### Session 4 — 2026-07-24 (Phase 1: Data Layer)
- Created `utils/netryx_loader.py` — .netryx ZIP reader, compact index loader, FAISS builder, bundle creator
- Created `utils/tile_downloader.py` — Google Street View tile fetcher with aiohttp + stitcher
- Created `utils/geo_utils.py` — haversine (scalar/vectorized), grid/circle generation, equirectangular projection
- Created `core/retrieval.py` — global FAISS/NumPy index singleton, radius-filtered cosine search
- Created `tests/generate_fixtures.py` — synthetic 50-entry .netryx bundle at `tests/fixtures/test_fixture_50.netryx`
- Created `scripts/test_retrieval.py` — end-to-end verification (load -> build -> search, 5/5 results returned)
### Session 5 — 2026-07-24 (Phase 2: Engine Abstraction)
- Created `engines/base.py` — `EngineBase` ABC with `run_stage2()` abstract method, `unload_models()` with CUDA/MPS cache clearing
- Created `engines/local_gpu.py` — `LocalGPUEngine(EngineBase)`: CUDA/MPS candidate loop with torch autocast, equirectangular crop on GPU, tile download + MASt3R matching per candidate, early exit at 450 inliers
- Created `engines/local_cpu.py` — `LocalCPUEngine(EngineBase)`: CPU candidate loop with PIL-based equirectangular crop, lower worker counts (8 vs 16), no autocast
- Created `core/matching.py` — `compute_matches()` wrapper around `mast3r_utils.get_mast3r_matches()`, lazy model singleton with `get_lazy_mast3r()` and `reset_model()`
- Updated `engines/__init__.py` — `auto_detect_engine(prefer)` factory: auto, gpu, mps, cpu with graceful fallback
- Added `pil_to_tensor()` / `tensor_to_pil()` to `utils/geo_utils.py` with device parameter
- Verified: both engines inherit EngineBase, factory + import chain works, all pass `ruff` + `mypy`
- **Next**: Phase 3 — Pipeline Integration (`core/consensus.py`, `core/pipeline.py`, hardware auto-detect)

## Session Checklist (End of Session)

- [x] PROGRESS.md updated with this session's work
- [x] ROADMAP.md reflects current phase
- [ ] No debugging artifacts left in codebase
- [ ] If files were created, verified with lint/typecheck if applicable
