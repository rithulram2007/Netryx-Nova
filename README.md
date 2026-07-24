<p align="center">
  <h1 align="center">Netryx Nova</h1>
  <p align="center"><strong>Modular image geolocation — forked from Netryx Astra V2.</strong></p>
  <p align="center">
    <a href="#overview">Overview</a> •
    <a href="#what-changed">What Changed</a> •
    <a href="#quick-start">Quick Start</a> •
    <a href="#architecture">Architecture</a> •
    <a href="#installation">Installation</a>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/MegaLoc-CVPR%202025-blue" alt="MegaLoc">
    <img src="https://img.shields.io/badge/MASt3R-ECCV%202024-green" alt="MASt3R">
    <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
    <img src="https://img.shields.io/badge/Python-3.10%2B-orange" alt="Python">
  </p>
</p>

---

Netryx Nova is a **complete modular refactoring** of [Netryx Astra V2](https://github.com/sparkyniner/Netryx-Astra-V2-Geolocation-Tool), a state-of-the-art image geolocation system by [Sairaj Balaji](https://www.linkedin.com/in/sairaj-balaji-7295b2246/). Given a single photograph — cropped, blurry, or metadata-free — it identifies precise GPS coordinates by matching visual features against a pre-indexed database of street-view panoramas.

The original was a 2800-line Tkinter monolith. Nova decouples it into **clean Python modules** with a FastAPI web UI, three execution engines (GPU / Cloud GPU / CPU), and on-the-fly FAISS vector search.

<p align="center">
  <img src="assets/demo.gif" width="800" alt="Netryx Nova in action">
</p>

## What Changed

| | Astra V2 (monolith) | Nova (modular) |
|---|---|---|
| **Architecture** | Single `test_super.py` (~2800 lines) | `core/`, `engines/`, `utils/`, `ui/` modules |
| **Web UI** | Tkinter desktop app | FastAPI + Leaflet.js + WebSocket |
| **Engine** | Inline pipeline | `EngineBase` ABC with GPU / Cloud / CPU backends |
| **Async** | Blocking | Async job model with 202 + WS streaming |
| **Consensus** | Inline heuristic | Pure NumPy grid clustering |
| **Index** | File-based | On-the-fly FAISS singleton (build at load) |
| **Cloud** | None | Modal.com T4 GPU worker |
| **Setup** | `pip install` | `pyproject.toml` with ruff + mypy + pytest |

## Pipeline

```
Query Image
     │
     ▼
┌────────────────┐
│  Stage 1       │  MegaLoc retrieval → top 1000 candidates
│  Retrieval     │  Radius filter → panoid dedup → 500 unique
└───────┬────────┘
        │
        ▼
┌────────────────┐
│  Stage 2       │  For each candidate:
│  Matching      │    Download panorama → crop → MASt3R match → score
│                │  Early exit at 450 inliers
└───────┬────────┘
        │
        ▼
┌────────────────┐
│  Stage 3       │  50m grid clustering → 3×3 neighborhood scoring
│  Consensus     │  sqrt(inlier) weighting → top-10 panoid-deduped
└───────┬────────┘
        │
        ▼
   📍 GPS coordinates
```

## Quick Start

```bash
# Clone the repo
git clone https://github.com/YOUR_USER/Netryx-Nova.git
cd Netryx-Nova

# Install dependencies
pip install -e .

# Download a community index or upload your own .netryx bundle
# Run the web server
python app.py

# Open http://localhost:8000
```

### Download a community index

```python
from netryx_hub import NetryxHub
hub = NetryxHub()
# List available indexes → download one
```

Or use the **Community Hub** sidebar in the web UI.

## Architecture

```
Netryx-Nova/
├── app.py                  # FastAPI entrypoint
├── config.py               # Thresholds, paths, tuning
├── core/
│   ├── consensus.py        # Grid clustering (pure NumPy)
│   ├── exceptions.py       # Custom exception classes
│   ├── matching.py         # MASt3R wrapper (lazy singleton)
│   ├── pipeline.py         # PipelineController (async job model)
│   └── retrieval.py        # FAISS singleton, radius search
├── engines/
│   ├── base.py             # EngineBase abstract class
│   ├── local_gpu.py        # CUDA/MPS engine
│   ├── local_cpu.py        # CPU fallback engine
│   └── cloud_modal.py      # Modal.com HTTP client
├── utils/
│   ├── geo_utils.py        # Haversine, projections, tensor ops
│   ├── netryx_loader.py    # .netryx bundle reader, FAISS builder
│   └── tile_downloader.py  # GSV tile fetcher (aiohttp, backoff)
├── ui/
│   ├── web_app.py          # APIRouter (7 endpoints + WS)
│   ├── templates/          # Jinja2 HTML
│   └── static/             # JS (Leaflet, WebSocket) + CSS
├── modal_app/
│   └── mast3r_worker.py    # Modal.com T4 GPU entrypoint
├── tests/                  # pytest suite (23 tests)
└── scripts/
    ├── test_retrieval.py   # End-to-end verification
    └── bench_retrieval.py  # FAISS latency benchmark
```

## Installation

### Requirements

- **Python 3.10+**
- **GPU** (recommended): NVIDIA CUDA, Apple Silicon MPS, or AMD ROCm
- **CPU**: Works, but Stage 2 (MASt3R) is significantly slower
- **8GB+ RAM** for searching

### Setup

```bash
pip install -e .
```

MASt3R must be cloned alongside the repo:

```bash
cd ..
git clone --recursive https://github.com/naver/mast3r.git
```

### Config

All tunable parameters live in `config.py`:

| Parameter | Default | Description |
|---|---|---|
| `RETRIEVAL_TOP_K` | 1000 | Raw FAISS candidates |
| `MATCHING_TOP_K` | 500 | Candidates sent to MASt3R |
| `EARLY_EXIT_INLIER_THRESHOLD` | 300 | Stop matching early at this score |
| `CELL_SIZE_DEG` | 0.00045 | Consensus grid cell size (~50m) |
| `CONSENSUS_TOP_K` | 10 | Final cluster results |

### Cloud GPU (Modal)

No GPU locally? Modal gives **$30 free credits** on first sign-up — enough for hundreds of searches on a T4.

```bash
pip install modal
modal setup
modal deploy modal_app/mast3r_worker.py
```

Set environment variables:

```
MODAL_TOKEN_ID=...
MODAL_TOKEN_SECRET=...
MODAL_WORKER_URL=https://your-worker.modal.run
```

Tokens can also be stored in `~/.modal.toml` — see [Modal docs](https://modal.com/docs/guide) for details.

### Run

```bash
python app.py
# → http://localhost:8000
```

## Tests

```bash
pytest tests/ -v
# 21 passed, 2 skipped (faiss not installed)
```

## License

MIT License. See [LICENSE](LICENSE) for details.

MegaLoc weights are MIT licensed. MASt3R is Apache 2.0 licensed. DINOv2 is Apache 2.0 licensed. Community-shared indexes are CC-BY-4.0.

---

<p align="center">
  <strong>Original work by <a href="https://www.linkedin.com/in/sairaj-balaji-7295b2246/">Sairaj Balaji</a></strong><br>
  Netryx Nova is a modular fork. All geolocation credit goes to the original Astra V2 pipeline.
</p>
