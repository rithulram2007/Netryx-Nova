# ROADMAP — Human-Logical Execution Order

Phase boundaries are chronological. Within each phase, tasks are listed in dependency order.

```
Phase 0: Project Skeleton & Tooling
Phase 1: Data Layer — .netryx Loader + FAISS Engine
Phase 2: Engine Abstraction — Base + Local GPU / CPU
Phase 3: Pipeline Integration — Controller + Consensus
Phase 4: Web UI — FastAPI + Leaflet Map
Phase 5: Cloud Deployment — Modal Worker + Client
Phase 6: Polish, Testing & Documentation
```

---

## Phase 0: Project Skeleton & Tooling

| # | Task | Target | Depends On |
|---|---|---|---|
| 0.1 | Create directory structure matching PRD spec | `app.py`, `config.py`, `core/`, `engines/`, `ui/`, ... | — |
| 0.2 | Set up `pyproject.toml` with ruff, mypy, pytest config | `pyproject.toml` | 0.1 |
| 0.3 | Create `config.py` extracting thresholds from existing code | `config.py` | 0.1 |
| 0.4 | Create `AGENTS.md` and context documentation system | `AGENTS.md`, `docs/` | — |

## Phase 1: Data Layer — .netryx Loader + FAISS Engine

| # | Task | Target | Depends On |
|---|---|---|---|
| 1.1 | Extract ZIP reader from netryx_hub.py into `utils/netryx_loader.py` | `utils/netryx_loader.py` | 0.1 |
| 1.2 | Implement on-the-fly FAISS index builder (load .npy -> IndexFlatIP) | `core/retrieval.py` | 1.1 |
| 1.3 | Implement FAISS search with cosine similarity + top-1000 retrieval | `core/retrieval.py` | 1.2 |
| 1.4 | Add global index singleton caching layer + dual mode (FAISS / legacy) | `core/retrieval.py` | 1.3 |
| 1.5 | Extract tile downloader with exponential backoff + rate-limiting | `utils/tile_downloader.py` | 0.1 |
| 1.6 | Generate synthetic test fixture (50 entries, mock .netryx) | `tests/generate_fixtures.py`, `tests/fixtures/` | 1.1 |

## Phase 2: Engine Abstraction

| # | Task | Target | Depends On |
|---|---|---|---|
| 2.1 | Create `EngineBase` abstract class with `run_stage2()` + `unload_models()` | `engines/base.py` | 0.1 |
| 2.2 | Implement `LocalGPUPipeline` engine (CUDA/MPS) | `engines/local_gpu.py` | 2.1 |
| 2.3 | Implement `LocalCPUPipeline` engine (CPU fallback) | `engines/local_cpu.py` | 2.1 |

## Phase 3: Pipeline Integration

| # | Task | Target | Depends On |
|---|---|---|---|
| 3.1 | Extract spatial consensus into `core/consensus.py` (pure NumPy, no engine dependency) | `core/consensus.py` | 1.4 |
| 3.2 | Implement PipelineController in `core/pipeline.py` — async job model, WS streaming | `core/pipeline.py` | 3.1 |
| 3.3 | Implement hardware auto-detect + fallback logic from PRD | `config.py` + engine init | 2.2, 2.3 |

## Phase 4: Web UI

| # | Task | Target | Depends On |
|---|---|---|---|
| 4.1 | Set up FastAPI app with CORS, static files, Jinja2 templates | `app.py`, `ui/web_app.py` | 0.1 |
| 4.2 | Build `ui/templates/index.html` with upload form + map container | `ui/templates/index.html` | 4.1 |
| 4.3 | Implement `ui/static/js/map.js` — Leaflet.js init, markers, polygons, GeoJSON layer | `ui/static/js/map.js` | 4.1 |
| 4.4 | Implement `ui/static/js/app.js` — WebSocket client, job tracking, status UI | `ui/static/js/app.js` | 4.1 |
| 4.5 | Create `ui/static/css/style.css` — dark theme, responsive layout | `ui/static/css/style.css` | 4.1 |
| 4.6 | Add API routes: `POST /api/v1/index/load` (multipart .netryx), `GET /api/v1/index/info`, `GET /api/v1/index/hub/list`, `POST /api/v1/index/hub/download` | `ui/web_app.py` | 4.1 |
| 4.7 | Add async search API: `POST /api/v1/search/run` -> 202 + `job_id`, `GET /api/v1/search/status/<job_id>`, `WS /api/v1/ws/search?job_id=<id>` | `ui/web_app.py` | 4.2, 3.2 |
| 4.8 | Integrate PipelineController with search routes — wired through WebSocket | `ui/web_app.py` + `core/pipeline.py` | 4.7, 3.2 |
| 4.9 | Add execution mode selector UI (Auto / Local GPU / Cloud / CPU) | `ui/templates/index.html` + `ui/static/js/app.js` | 4.2 |
| 4.10 | Add coverage map endpoint: `GET /api/v1/index/coverage` returns GeoJSON | `ui/web_app.py` + `ui/static/js/map.js` | 4.3, 4.6 |

## Phase 5: Cloud Deployment

| # | Task | Target | Depends On |
|---|---|---|---|
| 5.1 | Create Modal.com `@app.function(gpu="T4")` entrypoint | `modal_app/mast3r_worker.py` | — |
| 5.2 | Implement `engines/cloud_modal.py` — HTTP/gRPC client, retry, progress streaming | `engines/cloud_modal.py` | 5.1 |

## Phase 6: Polish, Testing & Documentation

| # | Task | Target | Depends On |
|---|---|---|---|
| 6.1 | Unit tests for retrieval.py (FAISS build + search) | `tests/test_retrieval.py` | 1.4 |
| 6.2 | Unit tests for consensus.py (clustering logic) | `tests/test_consensus.py` | 3.1 |
| 6.3 | Integration test: .netryx load -> FAISS -> search -> match (uses synthetic fixture) | `tests/test_pipeline.py` | 3.2, 1.6 |
| 6.4 | Unit tests for netryx_loader.py (bundle read, Optional PCA fallback, error cases) | `tests/test_netryx_loader.py` | 1.1 |
| 6.5 | Unit tests for tile_downloader.py (retry, rate-limit, empty response) | `tests/test_tile_downloader.py` | 1.5 |
| 6.6 | Benchmark script for Stage 1 latency across index sizes | `scripts/bench_retrieval.py` | 1.4 |
| 6.7 | Finalize ADR log and update all docs | `docs/2-decisions/` | all |
