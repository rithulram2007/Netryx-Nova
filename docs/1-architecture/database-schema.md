# Database Schema — .netryx Bundle Format & FAISS Index Structure

## .netryx Bundle Format

A `.netryx` file is a standard ZIP archive containing pre-computed index files for the MegaLoc geolocation pipeline.

### Archive Structure

```
archive.netryx
+-- manifest.json           # Required: metadata about the index
+-- descriptors.npy          # Required: PCA-reduced visual vectors (float32)
+-- metadata.npz             # Required: coordinate/heading/panoid lookup
+-- pca_model.pkl            # Optional (may be absent in older bundles)
+-- index_info.txt           # Optional: human-readable build info
```

### manifest.json Schema

```json
{
  "format_version": "2.0",
  "name": "Moscow Central 10km",
  "description": "Central Moscow coverage",
  "creator": "username",
  "created_at": "2026-07-24T12:00:00Z",
  "center_lat": 55.7539,
  "center_lon": 37.6208,
  "radius_km": 10.0,
  "num_entries": 184500,
  "num_panoids": 46125,
  "descriptor_dim": 1024,
  "raw_descriptor_dim": 8448,
  "descriptor_model": "MegaLoc",
  "pca_components": 1024,
  "heading_step_deg": 90,
  "crop_fov_deg": 90,
  "crop_size_px": 256,
  "tags": ["netryx", "geolocation", "moscow"],
  "sha256": "a1b2c3d4...",
  "file_size_bytes": 754000000
}
```

### descriptors.npy

- **Format**: NumPy array, `dtype=np.float32`, shape `(N, D)` where:
  - `N` = number of index entries (one per panorama-heading pair)
  - `D` = `descriptor_dim` from manifest (typically 1024)
- **Content**: PCA-reduced MegaLoc descriptors, L2-normalized after PCA transform.
- **Reading**: `np.load(path, mmap_mode='r')` — memory-mapped for large indexes.

### metadata.npz

NumPy archive with the following keys:

| Key | Type | Shape | Description |
|---|---|---|---|
| `lats` | float32 | `(N,)` | Latitude of each entry |
| `lons` | float32 | `(N,)` | Longitude of each entry |
| `headings` | int16 | `(N,)` | Compass heading in degrees (0-360) |
| `panoids` | object (str) | `(N,)` | Google Street View panorama ID (22 chars) |
| `paths` | object (str) | `(N,)` | Original embedding path (PANOID_HEADING.npz) |

### pca_model.pkl

Fitted `sklearn.decomposition.PCA` object with:
- `n_components_`: target dimension (e.g., 1024)
- `components_`: PCA rotation matrix (D_raw x D_target)
- `mean_`: feature mean for centering
- `explained_variance_ratio_`: variance explained per component

**Status: Optional.** Some older `.netryx` bundles may not include this file. The loader handles the absence as follows:
1. If PCA model is present: load and use for query-time transform (raw 8448-dim -> 1024-dim).
2. If PCA model is absent but `raw_descriptor_dim != descriptor_dim`: fall back to a global default PCA model path configured in `config.py`.
3. If PCA model is absent and `raw_descriptor_dim == descriptor_dim`: descriptors are already at target dimensionality — query path skips PCA entirely.

## FAISS In-Memory Index Structure

The FAISS index is **never serialized** — it is constructed at load time and exists only in RAM. It is held as a **global singleton** inside `core/retrieval.py`: loaded once by `POST /api/v1/index/load`, reused by all subsequent searches until a new index is loaded.

### Index Construction

```
Input: descriptors.npy (N x 1024, float32, L2-normalized)
Process: idx = faiss.IndexFlatIP(1024)  # Inner Product = cosine similarity
         idx.add(descriptors)
Output: faiss.IndexFlatIP object
```

### Search

```
Query: 1024-dim L2-normalized descriptor
Search: idx.search(query.reshape(1, -1), k=RETRIEVAL_TOP_K)   # 1000 by default
Output: (scores: float32[N], indices: int64[N])
```

### Performance Target

- N = 100,000+ vectors: search completed in < 50ms on CPU.
- N = 1,000,000+ vectors: search completed in < 500ms on CPU.

## Two-Tier Candidate Pipeline

After FAISS retrieval, candidates pass through a deduplication and filtering step:

```
FAISS: top 1000 raw candidates (RETRIEVAL_TOP_K)
  -> filter by radius (haversine)
  -> deduplicate by panoid (keep highest score per unique panoid)
  -> sort by score descending
  -> top 500 candidates (MATCHING_TOP_K)
  -> send to Stage 2 (MASt3R matching)
```

Both parameters live in `config.py`:
- `RETRIEVAL_TOP_K = 1000`
- `MATCHING_TOP_K = 500`

## Legacy .npy Fallback

When FAISS is unavailable (or disabled for memory-constrained environments), the existing chunked dot-product search in `search_compact_index()` is used instead. This loads descriptors via `mmap_mode='r'` and computes similarity in chunks of 100,000 vectors.

## Index Directory Layout (Runtime)

```
netryx_data/
+-- megaloc_parts/            # Raw 8448-dim descriptor chunks (indexing only)
|   +-- megaloc_part_*.npz
+-- index/                    # Compact search index (from build or download)
|   +-- megaloc_descriptors.npy
|   +-- metadata.npz
|   +-- megaloc_pca.pkl       # Optional
|   +-- manifest.json
|   +-- index_info.txt
```

## Bundle Extraction Filename Mapping

When a `.netryx` bundle is extracted, the internal filenames are mapped to runtime filenames:

| Bundle internal | Runtime location / name |
|---|---|
| `descriptors.npy` | In-memory array -> FAISS index |
| `metadata.npz` | `index/metadata.npz` |
| `pca_model.pkl` | `index/megaloc_pca.pkl` |
| `manifest.json` | `index/manifest.json` |
| `index_info.txt` | `index/index_info.txt` |
