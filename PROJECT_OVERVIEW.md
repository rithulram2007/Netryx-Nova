# PROJECT OVERVIEW — Netryx Nova

## Executive Summary

Netryx Nova is a modular fork of Netryx Astra V2, an open-source, state-of-the-art image geolocation system. Given a single photograph — even a cropped, blurry, or metadata-free image — it identifies the precise GPS coordinates by matching visual features against a pre-indexed database of street-view panoramas.

This edition is a **complete modular refactoring** of the original Netryx Astra V2 monolithic Tkinter codebase. It decouples the pipeline into clean Python modules, introduces an **on-the-fly FAISS vector indexer** for ultra-fast retrieval, replaces the legacy GUI with an **interactive Web UI (FastAPI + Leaflet.js)** featuring live map plotting, and supports **three execution engines**: Local GPU (CUDA/MPS), Serverless Cloud GPU (Modal.com), and Local CPU fallback.

## Target Audience

- **OSINT Investigators & Researchers** — precise geolocation from partial, cropped, or metadata-free images.
- **Developers & AI Engineers** — modular, headless, or web-based framework for visual place recognition experiments.

## Core Goals

- Maintain the full 3-stage visual localization pipeline without downscaling feature dimensions or truncating candidate evaluation.
- Refactor original single-file implementation (`test_super.py`, 2794 lines) into clean, testable Python modules.
- Ingest native `.netryx` index archives directly from the Hugging Face Community Hub without offline database conversion.
- Enable smooth execution across Local CUDA/MPS GPUs, Serverless Cloud GPUs (Modal.com), and Local CPUs via automatic fallback.
- Replace legacy Tkinter/PySimpleGUI elements with an interactive Web UI featuring integrated map visualization (Leaflet.js).

## System Architecture

```
                      +-----------------------------------------+
                      |       Web UI (FastAPI + Leaflet.js)    |
                      |  - Query Image Upload (Jinja2 form)    |
                      |  - Interactive Map (client-side JS)     |
                      |  - Hardware / Execution Mode Controls   |
                      |  - Real-time WS progress streaming     |
                      +-------------------+---------------------+
                                          |
                                          v
                      +-----------------------------------------+
                      |         PipelineController              |
                      |  (core/pipeline.py — async job model)   |
                      |  POST -> 202 Accepted + job_id          |
                      |  WS -> /api/v1/ws/search?job_id=<id>    |
                      +-------------------+---------------------+
                                          |
         +--------------------------------+--------------------------------+
         v                                v                                v
+-----------------------+      +-----------------------+      +-----------------------+
| Engine A: Local       |      | Engine B: Hybrid      |      | Engine C: Local       |
| CUDA / MPS GPU        |      | Modal Cloud API       |      | CPU (FAISS +          |
| (Max Performance)     |      | (Serverless T4)       |      | ONNX / OpenVINO)      |
+-----------------------+      +-----------------------+      +-----------------------+
         |                                |                                |
         v                                v                                v
+--------------------------------------------------------------------------+
|              Google Street View API (tile download, retry logic)          |
+--------------------------------------------------------------------------+
```

## Three-Stage Pipeline

### Stage 1: MegaLoc Visual Retrieval
Query image -> 8448-dim DINOv2 descriptor (3 variants: full, center-crop, flip) -> PCA 1024-dim -> FAISS cosine similarity search -> top `RETRIEVAL_TOP_K=1000` candidates.

### Stage 2: MASt3R Dense 3D Matching
For each candidate: download panorama -> crop at heading angle -> compute dense pixel correspondences between query and crop -> score by inlier count. Runs on top `MATCHING_TOP_K=500` deduplicated candidates.

### Stage 3: Spatial Consensus Clustering
Cluster matches into ~50m grid cells -> re-weight by spatial density -> eliminate isolated false positives (chain stores, repetitive architecture) -> output final GPS coordinates.

## Key Data Format: .netryx Bundle

ZIP archive containing:
- `megaloc_descriptors.npy` — PCA-reduced visual vectors (float32, N x 1024)
- `metadata.npz` — lat/lon/heading/panoid for every entry
- `megaloc_pca.pkl` — fitted sklearn PCA model (optional: missing bundles use default PCA or bypass)
- `manifest.json` — coverage metadata (center, radius, entry count, creator)

## Project Structure

```
netryx-astra-v2-refactored/
+-- config.py                   # Path resolution, thresholds, RETRIEVAL_TOP_K, MATCHING_TOP_K
+-- app.py                      # FastAPI entrypoint (routes, WS endpoints, startup)
+-- core/                       # Core algorithms
|   +-- pipeline.py             # PipelineController: async job orchestrator
|   +-- retrieval.py            # Stage 1: MegaLoc + on-the-fly FAISS (global singleton)
|   +-- matching.py             # Stage 2: MASt3R model wrapper, forward pass
|   +-- consensus.py            # Stage 3: spatial consensus clustering (pure NumPy)
+-- engines/                    # Compute execution strategies
|   +-- base.py                 # Abstract base class
|   +-- local_gpu.py            # CUDA / MPS native
|   +-- local_cpu.py            # CPU fallback
|   +-- cloud_modal.py          # Modal.com client
+-- modal_app/                  # Remote deploy code
|   +-- mast3r_worker.py        # Modal serverless entrypoint
+-- utils/                      # Helpers
|   +-- netryx_loader.py        # .netryx ZIP reader + FAISS builder
|   +-- tile_downloader.py      # Google tile downloader (backoff + rate-limit)
|   +-- geo_utils.py            # Haversine, grid, projection
+-- ui/                         # Web interface
|   +-- web_app.py              # FastAPI router
|   +-- templates/
|   |   +-- index.html          # Dashboard HTML
|   +-- static/
|       +-- css/
|       |   +-- style.css
|       +-- js/
|           +-- app.js          # WS client & UI state
|           +-- map.js          # Leaflet.js rendering
+-- docs/                       # Documentation (this system)
```

## Key Architecture Decisions

| Decision | Choice |
|---|---|
| Async search execution | `POST /api/v1/search/run` returns `202 Accepted` + `job_id` |
| Progress streaming | WebSocket `WS /api/v1/ws/search?job_id=<id>` |
| Map rendering | Client-side Leaflet.js (no Folium) |
| Index lifecycle | Global singleton in `core/retrieval.py`, loaded once |
| Two-tier candidate pipeline | `RETRIEVAL_TOP_K=1000` -> dedup -> `MATCHING_TOP_K=500` |
| PCA model in bundle | Optional — missing bundles use default PCA or bypass |
| Data directory order | Env var -> config override -> `./netryx_data` |
| VRAM on engine switch | `engine.unload_models()` -> `torch.cuda.empty_cache()` |

## Current Status (Pre-Refactor)

The existing codebase is a fully functional monolithic Tkinter app (2794-line `test_super.py`) implementing all 3 pipeline stages, panorama download/stitching, Community Hub integration, and a dark-themed GUI with tkintermapview. This refactoring preserves all functionality while modernizing the architecture.
