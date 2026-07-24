# API Specification

## Base URL

```
http://localhost:8000/api/v1
```

All endpoints are prefixed with `/api/v1`.

## Authentication

None. Netryx Astra V2 is a local-first tool. Hugging Face tokens for Community Hub uploads are passed as environment variables or form fields, not as API auth.

---

## Endpoints

### POST /api/v1/search/run

Trigger the full 3-stage geolocation pipeline. Returns immediately with a `job_id`. Progress is streamed via WebSocket.

**Request:**

```
Content-Type: multipart/form-data

image: <file>             # Required. JPEG/PNG, max 10MB
lat: float                # Optional. Search center latitude (default: from loaded index)
lon: float                # Optional. Search center longitude
radius_km: float          # Optional. Search radius (default: from loaded index)
engine: str               # Optional. "auto" | "local_gpu" | "local_cpu" | "cloud_modal" (default: "auto")
crop_fov: int             # Optional. Panorama crop field-of-view (default: 90)
crop_size: int            # Optional. Crop resolution (default: 256)
```

**Response (202 Accepted):**

```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "queued"
}
```

**Error Response (4xx):**

```json
{
  "detail": "No index loaded. Upload a .netryx file or load one via POST /api/v1/index/load."
}
```

---

### GET /api/v1/search/status/{job_id}

Poll the current state of a search job.

**Response:**

```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "running",
  "progress": {
    "phase": "matching",
    "current": 150,
    "total": 500
  },
  "best_match_so_far": {
    "lat": 55.7558,
    "lon": 37.6173,
    "inliers": 320
  }
}
```

**Status values:** `queued`, `running`, `complete`, `failed`, `cancelled`

**When complete:**

```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "complete",
  "result": {
    "lat": 55.7558,
    "lon": 37.6173,
    "heading": 180,
    "confidence": 0.94,
    "inliers": 452,
    "panoid": "a1b2c3d4e5f6g7h8i9j0k1",
    "cluster_size": 7
  },
  "candidates": [
    {"rank": 1, "lat": 55.7558, "lon": 37.6173, "heading": 180, "inliers": 452, "score": 0.94},
    {"rank": 2, "lat": 55.7560, "lon": 37.6180, "heading": 270, "inliers": 310, "score": 0.87}
  ],
  "timing_ms": {
    "stage1_retrieval": 45,
    "stage2_matching": 234000,
    "stage3_consensus": 12,
    "total": 234057
  }
}
```

---

### WebSocket /api/v1/ws/search

Query parameter: `job_id` (required)

Streams real-time progress and candidate match updates for a running search job.

**Server sends (sequential, one or more of each type):**

```json
{"type": "status", "message": "Loading index...", "job_id": "a1b2..."}
{"type": "progress", "phase": "retrieval", "current": 0, "total": 0, "job_id": "a1b2..."}
{"type": "progress", "phase": "matching", "current": 1, "total": 500, "job_id": "a1b2..."}
{"type": "match_update", "lat": 55.7558, "lon": 37.6173, "inliers": 320, "heading": 180, "crop_image": null, "current": 42, "total": 500, "job_id": "a1b2..."}
{"type": "complete", "result": {"lat": 55.7558, "lon": 37.6173, "inliers": 452, "heading": 180}, "candidates": [...], "job_id": "a1b2..."}
{"type": "error", "message": "MASt3R model failed to load", "job_id": "a1b2..."}
```

**Client can send:**

```json
{"type": "cancel"}
```

---

### POST /api/v1/index/load

Load a .netryx bundle into the global FAISS singleton.

**Request:**

```
Content-Type: multipart/form-data

file: <file>              # Required. .netryx bundle file
```

**Response (200):**

```json
{
  "status": "loaded",
  "name": "Moscow Central 10km",
  "num_entries": 184500,
  "num_panoids": 46125,
  "center": { "lat": 55.7539, "lon": 37.6208 },
  "radius_km": 10.0,
  "descriptor_dim": 1024,
  "faiss_index_type": "IndexFlatIP"
}
```

---

### GET /api/v1/index/info

Get metadata about the currently loaded index singleton.

**Response (200):**

```json
{
  "loaded": true,
  "name": "Moscow Central 10km",
  "num_entries": 184500,
  "num_panoids": 46125,
  "center": { "lat": 55.7539, "lon": 37.6208 },
  "radius_km": 10.0,
  "coverage_bounds": {
    "lat_min": 55.65,
    "lat_max": 55.85,
    "lon_min": 37.50,
    "lon_max": 37.75
  }
}
```

---

### GET /api/v1/index/coverage

Return coverage data as GeoJSON for map rendering.

**Response (200):**

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": { "type": "Point", "coordinates": [37.6173, 55.7558] },
      "properties": { "count": 4, "heading": 90 }
    }
  ],
  "metadata": {
    "name": "Moscow Central 10km",
    "num_points": 46125
  }
}
```

---

### POST /api/v1/index/hub/list

List available indexes from Hugging Face Community Hub.

**Request (optional filters):**

```json
{
  "city": "moscow",
  "limit": 20
}
```

**Response (200):**

```json
{
  "indexes": [
    {
      "name": "Moscow Central 10km",
      "repo_id": "username/netryx-moscow-10km",
      "radius_km": 10.0,
      "num_entries": 184500,
      "file_size_bytes": 754000000,
      "author": "username",
      "is_official": false
    }
  ]
}
```

---

### POST /api/v1/index/hub/download

Download an index from the Community Hub and load it into the global singleton.

**Request:**

```json
{
  "repo_id": "username/netryx-moscow-10km"
}
```

**Response (200):**

```json
{
  "status": "downloaded",
  "name": "Moscow Central 10km",
  "num_entries": 184500
}
```

---

### POST /api/v1/index/hub/upload

Upload the currently loaded index to the Community Hub.

**Request (multipart form):**

```
Content-Type: multipart/form-data

city: str                 # Required. City name
radius_km: float          # Required. Coverage radius
center_lat: float         # Required. Center latitude
center_lon: float         # Required. Center longitude
hf_token: str             # Required. Hugging Face write token
tags: str                 # Optional. Comma-separated tags
```

**Response (200):**

```json
{
  "status": "uploaded",
  "url": "https://huggingface.co/datasets/username/netryx-moscow-10km",
  "name": "Moscow 10km"
}
```

---

## Error Codes

| Code | Description |
|---|---|
| 400 | Invalid request (missing image, bad coordinates) |
| 404 | No index loaded or job_id not found |
| 413 | Image too large (>10MB) |
| 422 | Unprocessable entity (validation error) |
| 500 | Pipeline error (model load failure, OOM, etc.) |
| 503 | Modal.com unavailable (cloud engine selected but no credentials) |
