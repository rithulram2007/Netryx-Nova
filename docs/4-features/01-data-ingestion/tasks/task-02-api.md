# Task 02: On-the-Fly FAISS Index Builder & Two-Tier Search

## Target Files

- `core/retrieval.py` (new)
- `tests/test_retrieval.py` (new)

## Description

Build an in-memory FAISS `IndexFlatIP` from descriptors loaded by `netryx_loader`, then implement the search method that combines MegaLoc descriptor extraction, PCA transform, FAISS query, and two-tier candidate filtering (`RETRIEVAL_TOP_K=1000` -> dedup -> `MATCHING_TOP_K=500`) into a single pipeline step.

## Checklist

- [ ] Implement global index singleton: `_faiss_index = None`, `_metadata = None`, `_pca_model = None`
- [ ] Implement `load_index(bundle: IndexBundle)` — replaces the global singleton
- [ ] Implement `unload_index()` — clears singleton, frees memory
- [ ] Implement `build_faiss_index(descriptors: np.ndarray) -> faiss.Index`
  - Validate input is float32 and L2-normalized
  - Create `faiss.IndexFlatIP(dim)` or `IndexHNSWFlat(dim, 32)` for larger indexes
  - Add vectors via `index.add(descriptors)`
- [ ] Implement `search_index(index, query_desc, k=RETRIEVAL_TOP_K) -> Tuple[scores, indices]`
  - Ensure query is float32, L2-normalized
- [ ] Implement `extract_and_search(image, metadata, center, radius_km) -> List[dict]`
  - Call MegaLoc descriptor extraction (3 variants: full, zoom, flip)
  - Average with 0.65/0.35 weighting
  - Transform via PCA if model present
  - L2-normalize
  - FAISS search with k=RETRIEVAL_TOP_K
  - Haversine radius filter
  - Panoid dedup (keep highest score per unique panoid)
  - Return top MATCHING_TOP_K unique panoids with metadata
- [ ] Implement legacy fallback `chunked_dot_product_search(...)` for non-FAISS environments
- [ ] Measure and log Stage 1 timing

## Verification

```bash
pytest tests/test_retrieval.py -v
python -c "
from core.retrieval import build_faiss_index, search_index
import numpy as np
descs = np.random.randn(1000, 1024).astype(np.float32)
descs /= np.linalg.norm(descs, axis=1, keepdims=True)
idx = build_faiss_index(descs)
scores, indices = search_index(idx, descs[0])
print(f'Top match score: {scores[0]:.4f}')
"
```
