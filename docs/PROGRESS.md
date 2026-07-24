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

### Session 6 — 2026-07-24 (Phase 3: Pipeline Integration)
- Added pipeline constants to `config.py`: `CELL_SIZE_DEG`, `CONSENSUS_TOP_K`, `MAX_CONCURRENT_GPU_JOBS`, `MAX_CONCURRENT_CPU_JOBS`, `JOB_CLEANUP_TIMEOUT_SECONDS`
- Created `core/consensus.py` — pure NumPy spatial clustering: grid cells at 0.00045° (~50m), 3x3 neighborhood scoring with sqrt(inlier) weighting, top-10 panoid-deduped ranking
- Created `core/pipeline.py` — `PipelineController` with full async job lifecycle: queued → running → complete|failed|cancelled, WS progress queue, cancellation via `threading.Event`, engine slot management (1 GPU / 2 CPU concurrent), background stale-job cleanup loop
- Updated `engines/base.py` — added `match_collector` param to `run_stage2()` so controllers can collect all scored matches for consensus without coupling to internal `_build_result`
- Updated `engines/local_gpu.py` / `local_cpu.py` — populate `match_collector` when provided
- Verified with `ruff` + `mypy` (zero errors across all new/changed files)
- Committed as: `feat(pipeline): add PipelineController, consensus module, and hardware auto-detect`
- **Next**: Phase 4 — Web UI (FastAPI routes, Leaflet map, WebSocket handler)

### Session 7 — 2026-07-24 (Phase 4: Web UI)
- Created `ui/web_app.py` — FastAPI `APIRouter` with 7 endpoints: `POST /api/v1/index/load` (multipart .netryx upload), `GET /api/v1/index/info` (loaded index stats), `GET /api/v1/index/hub/list` (community indexes), `POST /api/v1/index/hub/download` (from HF Hub), `POST /api/v1/search/run` → 202 + job_id (image + lat/lon/radius), `GET /api/v1/search/status/{job_id}` (polling), `WS /api/v1/ws/search` (real-time progress via job progress_queue), `GET /api/v1/index/coverage` (GeoJSON point cloud)
- Created `ui/templates/index.html` — single-page app: dark theme, sidebar (upload zone, community hub list, search form with lat/lon/radius + image picker + engine selector), Leaflet map container, progress bar, ranked results panel
- Created `ui/static/js/map.js` — Leaflet init with CartoDB dark tiles, `addCandidate()` / `addClusterMarker()` / `flyTo()` / `loadCoverage()`
- Created `ui/static/js/app.js` — WebSocket client: connects after search, processes `status`/`progress`/`complete`/`error` messages, updates progress bar, renders result cards with click-to-fly interaction, cancel support, upload drag-and-drop, hub download
- Created `ui/static/css/style.css` — full dark theme (CSS variables), flex layout, upload drag-drop zone, form styling, progress bar, result cards, Leaflet overrides
- Updated `app.py` — Jinja2Templates + StaticFiles mount, router inclusion, root route with `request` injection
- Verified: `ruff` clean, all 14 routes registered (import check passed)
- Committed as: `feat(web-ui): add FastAPI routes, Leaflet map, WebSocket client, dark theme`
### Session 8 — 2026-07-24 (Rename: Netryx Nova)
- Renamed project from "Netryx Astra V2" to **Netryx Nova**
- Updated: `app.py`, `pyproject.toml`, `AGENTS.md`, `PROJECT_OVERVIEW.md`, `ui/templates/index.html`,
  `setup.bat`, `setup.sh`, `core/exceptions.py`, `docs/1-architecture/system-design.md`,
  `docs/3-api/api-spec-template.md`, `docs/PROGRESS.md`
- **Next**: Phase 5 — Cloud Deployment (Modal worker, CloudModalEngine)

### Session 9 — 2026-07-24 (Phase 5: Cloud Deployment)
- Created `modal_app/mast3r_worker.py` — Modal FastAPI ASGI entrypoint with T4 GPU, auto-detect MASt3R at deploy/runtime, `/match` endpoint (download tiles → stitch → crop → MASt3R), `/health` endpoint, local dev mode on :8001
- Created `engines/cloud_modal.py` — `CloudModalEngine(EngineBase)`: HTTP client dispatching candidates to Modal worker with 3-retry exponential backoff, candidate loop with early exit, `match_collector` support, `available()` static check via env vars
- Updated `engines/__init__.py` — `auto_detect_engine()` now falls through to CloudModalEngine when GPU unavailable and `MODAL_TOKEN_ID`/`SECRET` are set; explicit `"cloud"` mode supported
- Updated `core/pipeline.py` — `set_engine("cloud")` instantiates `CloudModalEngine` directly
- Updated `ui/templates/index.html` — added "Cloud GPU" to engine selector dropdown
- Verified: `ruff` + `mypy` clean, CloudModalEngine import/instantiation OK
- Committed as: `feat(cloud): add Modal GPU worker and CloudModalEngine client`
- **Next**: Phase 6 — Polish, Testing & Documentation

## Session Checklist (End of Session)
- [x] ROADMAP.md reflects current phase
- [ ] No debugging artifacts left in codebase
- [ ] If files were created, verified with lint/typecheck if applicable
