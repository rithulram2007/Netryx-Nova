# ADR-001: Tech Stack & Architecture Decisions

## Status

Accepted

## Context

The original Netryx Astra V2 is a fully functional monolithic Tkinter application (2794 lines in `test_super.py`). We are refactoring it into a modular, multi-engine, web-based architecture. Several fundamental decisions affect the entire codebase.

## Decision 1: FastAPI + Leaflet.js over Gradio

**Decision:** Use FastAPI with client-side Leaflet.js maps.

**Rationale:**
- Gradio's built-in components are limited for interactive map manipulation (pan, zoom, marker clustering).
- FastAPI provides type-validated request/response via Pydantic, OpenAPI docs, and WebSocket support for streaming match progress.
- Leaflet.js gives full control over map layer styling (dark theme tiles, clustered markers, dynamic polygon overlays).
- Folium explicitly rejected — server-side HTML injection creates bottlenecks and couples rendering to Python. Instead, FastAPI serves JSON/GeoJSON and Leaflet renders client-side.

**Consequences:**
- (+) Full control over UI layout and map interactivity.
- (+) WebSocket streaming for real-time candidate match updates.
- (+) Production-grade async server (Uvicorn).
- (-) More frontend code needed compared to Gradio's auto-generated UI.

## Decision 2: On-the-Fly FAISS Index (No Serialization, Global Singleton)

**Decision:** Build FAISS `IndexFlatIP` from `.npy` descriptors at load time; never serialize the FAISS index to disk. Hold the index as a global singleton in `core/retrieval.py`.

**Rationale:**
- `.npy` files are already the persistent format — duplicating as FAISS serialization adds complexity.
- Loading 100k vectors into FAISS takes < 1 second.
- FAISS index format changes across versions (IVF, HNSW parameters) would create compatibility issues.
- The existing chunked dot-product search remains as a fallback for environments without FAISS.
- Singleton pattern avoids redundant FAISS rebuilds on every search request.

**Consequences:**
- (+) Zero migration needed for existing `.netryx` bundles.
- (+) Simple deployment — no FAISS index files to manage.
- (-) ~100ms load time penalty per index load.
- (-) FAISS index rebuilt on every app restart or explicit reload.

## Decision 3: Full Web Migration (Drop Tkinter)

**Decision:** Replace Tkinter entirely with FastAPI + Leaflet.js. No legacy Tkinter code will remain.

**Rationale:**
- Tkinter's custom widgets (RoundedButton, RoundedEntry, etc.) are hundreds of lines of boilerplate that achieve what HTML/CSS does trivially.
- `tkintermapview` is EOL and has no path for future map feature additions.
- Web UI enables headless/API-only usage, cross-platform consistency, and remote access.

**Consequences:**
- (+) Modern, extensible UI with standard web technologies.
- (+) API-first design enables CLI scripts and integration with other tools.
- (-) Loss of native desktop feel (no system tray, no local file drag-drop without browser config).

## Decision 4: Drop MixVPR Encoder

**Decision:** Remove MixVPR encoder support. Only MegaLoc will be supported.

**Rationale:**
- MixVPR was a fallback for resource-constrained environments that Local CPU Engine now covers.
- Dual-encoder support doubles testing surface, index storage paths, and documentation complexity.
- The PRD explicitly specifies MegaLoc only.

**Consequences:**
- (+) Simplified codebase: one retrieval encoder, one descriptor pipeline, one index format.
- (-) Existing MixVPR indexes from Community Hub will need MegaLoc re-indexing (community coordination required).

## Decision 5: Extract Existing Spatial Consensus Algorithm

**Decision:** Extract the proven spatial consensus clustering from `test_super.py` into `core/consensus.py` with minimal changes.

**Rationale:** The existing algorithm (50m grid cells, 3x3 neighborhood scoring, sqrt-inlier weighting) has been validated through production use. Rewriting from scratch risks introducing regressions with no accuracy benefit. Consensus is pure NumPy — it has no dependency on engine abstraction or GPU hardware.

**Consequences:**
- (+) Proven accuracy preserved.
- (+) Faster implementation — extraction is mechanical, not algorithmic.
- (+) Consensus can be developed independently of engines (no coupling).
- (-) Legacy code patterns (no OOP, mixed numpy/python loops) preserved until a future optimization pass.

## Decision 6: Engine-Agnostic Base Docs + Modal-Specific Appendix

**Decision:** The engine abstraction (`engines/base.py`) defines a purely abstract interface with `run_stage2()` and `unload_models()`. Modal.com specifics (API keys, `@app.function` decorator patterns, deployment) are documented separately in `modal_app/`.

**Consequences:**
- (+) Adding future providers (RunPod, Banana, TensorRT) requires zero changes to pipeline or docs.
- (+) Modal deployment docs stay co-located with Modal code.
- (+) `unload_models()` enables clean VRAM management across engine switches.

## Decision 7: Asynchronous Search Execution (ADR-002 adopted)

**Decision:** All search operations will be fully asynchronous. `POST /api/v1/search/run` returns `202 Accepted` with a `job_id`. Clients connect via WebSocket for progress. This replaces the original synchronous blocking approach.

**Rationale:** Stage 2 (MASt3R matching) takes 2-4 minutes. Synchronous HTTP would timeout all standard client connections.

**Consequences:**
- (+) Eliminates client HTTP timeouts.
- (+) Fine-grained progress streaming to UI.
- (-) Requires WebSocket infrastructure and client-side connection management.

## Decision 8: Google Street View API Risk Acceptance

**Context:** The existing pipeline depends on undocumented Google internal endpoints (`streetviewpixels-pa.googleapis.com` for tile downloads, `maps.googleapis.com/maps/api/js/GeoPhotoService.SingleImageSearch` for panorama discovery). These are not official APIs and have no SLA.

**Decision:** Accept the dependency risk and implement defensive measures:
1. Exponential backoff retry handler in `utils/tile_downloader.py` (2s, 4s, 8s, max 3 retries).
2. Rate-limiting lock (max 64 concurrent tile connections) to avoid IP bans.
3. Browser-like User-Agent and Referer headers to reduce 403 responses.
4. Document this as a known limitation in user-facing help.

**Consequences:**
- (+) No immediate alternative — Google Street View is the only comprehensive global street-level imagery source.
- (-) If Google changes internal APIs, the pipeline breaks until the new endpoint format is reverse-engineered.
- (-) Not deployable as a public SaaS — violates Google ToS for commercial use.
