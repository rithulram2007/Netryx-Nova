# System Design — Component Architecture

## C4 Context Diagram

```
[User: OSINT Investigator]
    |
    | (uploads photo via browser, sees Leaflet map)
    v
[Netryx Nova (FastAPI)] --- fetches panoramas ---> [Google Street View API]
    |
    | (downloads indexes, uploads new ones)
    v
[Hugging Face Hub] --- hosts .netryx bundles ---> [Community Contributors]
    |
    | (offloads GPU MASt3R inference)
    v
[Modal.com] --- serverless T4 GPU ---> [Cloud MASt3R Worker]
```

## Container Diagram

```
+--------------------------------------------------------------------+
|                    FastAPI Web Application                          |
|  +------------------+  +--------------------+  +-----------------+  |
|  |  ui/web_app.py   |  | core/pipeline.py   |  | config.py       |  |
|  |  (routes, WS,    |  | PipelineController |  | (thresholds,    |  |
|  |   templates)     |  | async job state    |  |  paths, modes)  |  |
|  +--------+---------+  +---------+----------+  +-----------------+  |
|           |                       |                                  |
|           v                       v                                  |
|  +------------------+  +--------------------+                        |
|  |  ui/static/     |  |  core/retrieval.py |                        |
|  |  js/app.js      |  |  (FAISS singleton) |                        |
|  |  js/map.js      |  |  (MegaLoc model)   |                        |
|  |  css/style.css  |  |  (PCA transform)   |                        |
|  +------------------+  +--------------------+                        |
+--------------------------------------------------------------------+
            |                              |
            v                              v
+-------------------------+   +---------------------------+
|    engines/base.py      |   |   core/matching.py        |
|    LocalGPUEngine       |   |   (MASt3R model wrapper)  |
|    LocalCPUEngine       |   |   (forward pass only)     |
|    CloudModalEngine     |   +---------------------------+
+-------------------------+               |
            |                              |
            v                              v
+-------------------------+   +---------------------------+
|   core/consensus.py     |   |   utils/tile_downloader   |
|   (pure NumPy density   |   |   (backoff + rate-limit)  |
|    clustering)          |   +---------------------------+
+-------------------------+
```

## Module Responsibility Boundaries

| Module | File | Owns | Does NOT own |
|---|---|---|---|
| Matching | `core/matching.py` | MASt3R forward pass, pair tensor preprocessing, raw point map extraction | Candidate iteration loop, tile download, score aggregation |
| Local GPU Engine | `engines/local_gpu.py` | CUDA/MPS device management, candidate loop, batching strategy, `unload_models()` | MASt3R model instantiation, PCA transform |
| Cloud Modal Engine | `engines/cloud_modal.py` | Remote HTTP/gRPC invocation to Modal, retry mechanics, payload serialization | MASt3R inference engine, panorama cropping |
| Pipeline | `core/pipeline.py` | Stage 1 -> 2 -> 3 orchestration, WebSocket job status streams, engine selection | Model loading, tile download, map rendering |
| Consensus | `core/consensus.py` | Grid clustering, density scoring, cluster ranking | Knowledge of where match scores came from |

## Component Interaction Flows

### Async Search Flow

```
1. User uploads query image via Web UI form
2. FastAPI route POST /api/v1/search/run:
   - Validates image, lat, lon, radius
   - Creates job_id (uuid)
   - Spawns background thread via PipelineController
   - Returns 202 Accepted { "job_id": "uuid", "status": "queued" }
3. Client connects WS /api/v1/ws/search?job_id=<uuid>
4. PipelineController (in background thread):
   a. core/retrieval.py:
      - Loads .netryx via utils/netryx_loader.py (if not already cached)
      - Builds on-the-fly FAISS IndexFlatIP (or uses existing singleton)
      - Extracts MegaLoc descriptor (3 variants: full, zoom, flip)
      - Merges and averages descriptors (0.65/0.35 zoom weighting)
      - Searches FAISS index -> top 1000 raw candidates
      - Filters by radius -> deduplicates by panoid -> top 500 unique panoids
      - WS push: {"type": "status", "message": "Stage 1 complete — 500 candidates", "progress": {"current": 0, "total": 500}}
   b. engines/<selected>.py:
      - For each candidate:
        - Download panorama tiles via utils/tile_downloader.py (with backoff)
        - Stitch tiles -> crop at heading angle
        - Run MASt3R dense matching via core/matching.py
        - Score by inlier count
        - WS push: {"type": "match_update", "lat": ..., "lon": ..., "inliers": ..., "current": i, "total": 500}
        - Check cancel flag (client can send WS cancel message)
   c. core/consensus.py:
      - Grid-based spatial clustering at ~50m resolution (0.00045 deg cells)
      - 3x3 neighborhood scoring with sqrt(inlier) weighting
      - Top-10 cluster ranking with panoid dedup
      - WS push: {"type": "complete", "result": {...}, "candidates": [...]}
```

### Engine Selection Flow

```
                  +---------------------------+
                  |  Auto-Detect Mode?        |
                  +-----+---------------------+
                        |
              +---------+----------+
              |                    |
              v                    v
   +-------------------+  +-------------------+
   | CUDA/MPS avail?   |  | Manual Override?  |
   +--+----------------+  +--+----------------+
      | YES                  | (selected engine)
      v                      v
   LocalGPUEngine         [selected engine]
      |                     |
      | (if fails)          | (if fails)
      v                     v
   +-----------------------------------+
   | MODAL_TOKEN_ID + MODAL_TOKEN_SECRET set?  |
   +--+--------------------------------+
      | YES
      v
   CloudModalEngine
      |
      | (if fails or no creds)
      v
   LocalCPUEngine (guaranteed fallback — emits warning notification)
```

### Engine Switch / VRAM Management

```
PipelineController.set_engine("cloud_modal"):
  1. if current_engine is LocalGPUEngine:
     current_engine.unload_models()           # torch.cuda.empty_cache()
     gc.collect()
  2. new_engine = CloudModalEngine(...)
  3. current_engine = new_engine
```

## Key Design Decisions

- **FAISS built on-the-fly**: `IndexFlatIP` constructed from `megaloc_descriptors.npy` at load time. Never serialized to disk. Held as **global singleton** in `core/retrieval.py` — `POST /api/v1/index/load` replaces the singleton; subsequent searches reuse it.
- **Async execution**: Search returns `202 Accepted` immediately. Clients must connect via WebSocket for real-time progress. Sync polling available via `GET /api/v1/search/status/<job_id>`.
- **Two-tier candidates**: `RETRIEVAL_TOP_K=1000` (FAISS) -> panoid dedup -> `MATCHING_TOP_K=500` (MASt3R). The extra margin accounts for horizontal flip duplicates and crop variations.
- **Engine abstraction**: `EngineBase` defines `run_stage2(candidates, query_img) -> scored_candidates` and `unload_models()`. PipelineController selects one at startup based on availability + config. Only one GPU engine active at a time.
- **PCA in query path only**: Index descriptors are already PCA-reduced (stored at 1024 dim). PCA model from .netryx bundle is optional — if missing, a global default PCA is used, or the query path runs without PCA if descriptors were pre-projected before storage.
- **Leaflet.js client-side rendering**: FastAPI serves GeoJSON coordinate clusters via REST endpoints. `ui/static/js/map.js` handles all map rendering (markers, tile layers, polygons) natively in the browser. No Folium server-side HTML injection.
- **Tile download resilience**: `utils/tile_downloader.py` implements exponential backoff (2s, 4s, 8s) on HTTP 429/5xx, rate-limiting locks (max 64 concurrent), and browser-like headers to reduce 403 risk.
- **Spatial consensus algorithm** (extracted from existing code): 50m grid cells (0.00045 deg), 3x3 neighborhood scoring with sqrt(inlier) weighting, top-10 cluster ranking with panoid dedup.
