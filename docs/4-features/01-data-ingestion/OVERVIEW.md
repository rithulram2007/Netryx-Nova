# Feature: Data Ingestion & On-the-Fly FAISS Indexing

## Overview

This feature covers loading `.netryx` index bundles and building an in-memory FAISS vector index for Stage 1 retrieval. It is the foundation that all downstream pipeline stages depend on.

## Business Logic

1. **Bundle Extraction**: Read ZIP archive, validate manifest, extract files mapping bundle names to runtime names (`descriptors.npy` -> FAISS array, `pca_model.pkl` -> `megaloc_pca.pkl`).
2. **FAISS Index Construction**: Load PCA-reduced descriptors into `faiss.IndexFlatIP` (inner product = cosine similarity for L2-normalized vectors). Held as a global singleton in `core/retrieval.py` — rebuilds only on explicit `POST /api/v1/index/load`.
3. **PCA Model Loading**: Load the fitted PCA model from the bundle. **Optional** — if absent from the bundle:
   - If `raw_descriptor_dim != descriptor_dim`: fall back to a global default PCA path from `config.py`.
   - If `raw_descriptor_dim == descriptor_dim`: descriptors are already at target dimensionality — skip PCA.
4. **Dual Mode Support**: FAISS is the default. Legacy chunked dot-product search remains as fallback for environments where FAISS is unavailable.
5. **Two-Tier Candidate Pipeline**: FAISS returns `RETRIEVAL_TOP_K=1000` raw candidates. After radius filtering and panoid dedup, top `MATCHING_TOP_K=500` are sent to Stage 2.
6. **Metadata Cache**: Lats, lons, headings, and panoids are loaded into memory for radius filtering and result display.

## Key Config (config.py)

```python
RETRIEVAL_TOP_K = 1000    # Raw candidates from FAISS
MATCHING_TOP_K = 500      # Deduplicated candidates to Stage 2
DEFAULT_PCA_PATH = None   # Fallback PCA if bundle lacks pca_model.pkl
```

## Key Files

| File | Purpose |
|---|---|
| `utils/netryx_loader.py` | ZIP reader, manifest validation, bundle extraction, Optional PCA handling |
| `core/retrieval.py` | FAISS singleton, index builder, search method, PCA transform, legacy fallback |

## Dependencies

- `numpy` for descriptor loading
- `faiss-cpu` (or `faiss-gpu`) for vector index
- `scikit-learn` for PCA loading
- `zipfile` (stdlib) for bundle extraction

## Verification

```bash
pytest tests/test_netryx_loader.py -v
pytest tests/test_retrieval.py -v
python -c "from utils.netryx_loader import load_bundle; m = load_bundle('tests/fixtures/test_1km.netryx'); print(len(m.descriptors))"
```
