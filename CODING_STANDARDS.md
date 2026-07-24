# CODING STANDARDS — Tech Stack, Conventions & Patterns

## Language & Runtime

- **Python 3.10+** — type annotations required on all function signatures and public methods.
- **Node.js 18+** — only if frontend build tooling is introduced (future).

## Tech Stack

| Layer | Technology | Rationale |
|---|---|---|
| Web Framework | FastAPI + Uvicorn | Async-native, automatic OpenAPI docs, production-grade |
| Map Visualization | **Leaflet.js** (client-side, via `ui/static/js/map.js`) | Interactive, lightweight, no API key needed. FastAPI serves GeoJSON; Leaflet renders. Folium explicitly NOT used — no server-side HTML injection. |
| ML Runtime | PyTorch 2.x | CUDA/MPS/CPU, bfloat16 autocast, torch.compile |
| Vector Search | FAISS (IndexFlatIP / IndexHNSWFlat) | On-the-fly cosine similarity, sub-50ms on 100k+ vectors |
| PCA | scikit-learn | Used in existing codebase for 8448->1024 dim reduction |
| Image Processing | Pillow | Panorama stitching, crop, resize (OpenCV not used) |
| Async HTTP | aiohttp | Tile download, panoramic fetch |
| Serverless GPU | Modal.com SDK | `@app.function(gpu="T4")` for cloud MASt3R offload |
| Templates | Jinja2 (via FastAPI) | Server-rendered HTML for initial page load |

## Module Architecture (PRD-mandated, with fixes applied)

```
app.py                          # FastAPI entrypoint (routes, WS endpoints, startup)
config.py                       # Path resolution, thresholds, top_k, data dir order
core/                           # Core algorithms — NO network or UI code
  pipeline.py                   # PipelineController: orchestrates stages 1-3, manages async jobs
  retrieval.py                  # Stage 1: MegaLoc + FAISS search (global singleton index)
  matching.py                   # Stage 2: MASt3R model wrapper, tensor forward pass, point maps
  consensus.py                  # Stage 3: pure NumPy spatial clustering (no engine dependency)
engines/                        # Compute execution strategies
  base.py                       # Abstract EngineBase with run_stage2() + unload_models()
  local_gpu.py                  # CUDA/MPS candidate loop, batching, VRAM management
  local_cpu.py                  # CPU-optimized execution provider
  cloud_modal.py                # Modal.com RPC/HTTP client adapter
modal_app/                      # Remote deployment code (separate deploy context)
  mast3r_worker.py              # Modal @app.function(gpu="T4") entrypoint
utils/                          # Shared helpers
  netryx_loader.py              # .netryx ZIP bundle reader + FAISS builder (non-destructive)
  tile_downloader.py            # Google Street View tile fetcher with exponential backoff + rate limiting
  geo_utils.py                  # Haversine, grid generation, equirectangular projection
ui/                             # Web interface
  web_app.py                    # FastAPI router: mounts templates + static, defines API routes
  templates/
    index.html                  # Dashboard HTML (Jinja2)
  static/
    css/
      style.css                 # Application styles
    js/
      app.js                    # WebSocket client, UI state machine, job tracking
      map.js                    # Leaflet.js map init, markers, polygons, GeoJSON rendering
```

## Module Responsibility Boundaries

| Module | Owns | Does NOT own |
|---|---|---|
| `core/matching.py` | MASt3R forward pass, pair tensor preprocessing, raw point map extraction | Candidate iteration loop, tile download, score aggregation |
| `engines/local_gpu.py` | CUDA/MPS device management, candidate loop, batching strategy, `unload_models()` | MASt3R model instantiation, PCA transform |
| `engines/cloud_modal.py` | Remote HTTP/gRPC invocation to Modal, retry mechanics, payload serialization | MASt3R inference engine, panorama cropping |
| `core/pipeline.py` | Orchestrates Stage 1 -> Stage 2 -> Stage 3; manages WebSocket job status streams | Model loading, tile download, map rendering |
| `core/consensus.py` | Grid clustering, density scoring, cluster ranking | Knowledge of where match scores came from (GPU/Cloud/CPU) |

## Coding Conventions

### Imports
- Standard library -> third-party -> local modules (separated by blank line).
- No `from module import *`.
- Lazy imports inside functions for heavy modules (torch, faiss) to keep startup fast.

### Types
- Every public function must have type annotations.
- Use `numpy.typing.NDArray` for numpy arrays, `torch.Tensor` for tensors.
- Use `dataclass` or `TypedDict` for structured data passing between pipeline stages.

### Error Handling
- Custom exceptions in `core/exceptions.py` for pipeline-specific errors.
- Engine selection failures must not crash the app — fall back gracefully.
- All async route handlers should have try/except with proper HTTP status codes.

### Performance
- Use `mmap_mode='r'` for loading large descriptor arrays (multi-GB).
- FAISS index built on-the-fly — never serialize to disk.
- FAISS index held as global singleton in `core/retrieval.py` — loaded once, searches reuse.
- MASt3R inference runs in a thread pool; never block the event loop.
- Batch MegaLoc descriptor extraction (default batch size: 64).

### VRAM Management
- Engine switches trigger `engine.unload_models()` -> `torch.cuda.empty_cache()` / `torch.mps.empty_cache()` + `gc.collect()`.
- Only one GPU engine active at a time.

### Data Directory Resolution (in config.py)

1. Environment variable `NETRYX_DATA_DIR`
2. Config file override in `config.json`
3. Local fallback `./netryx_data`

## Do's and Don'ts

| Do | Don't |
|---|---|
| Use `.reshape()` over `.view()` for MPS compatibility | Hardcode device strings |
| L2-normalize after PCA transform | Modify .netryx archives in-place |
| Use `torch.amp.autocast` for inference | Import Tkinter anywhere |
| Log pipeline stage timing to stdout | Write monolithic single-file modules |
| Abstract engine selection behind base class | Duplicate matching logic per engine |
| Return `202 Accepted` for long-running searches | Block HTTP response for >30s |
| Use `RETRIEVAL_TOP_K` and `MATCHING_TOP_K` separately | Hardcode candidate counts |

## Testing

- Unit tests in `tests/` mirroring the package structure.
- `pytest` with `--tb=short` for readability.
- Integration tests for the full pipeline require a small .netryx fixture (generated by `tests/generate_fixtures.py`: 50 synthetic 1024-dim vectors with valid lat/lon).
