# ADR-002: Pipeline Controller & Asynchronous Execution Model

## Status

Accepted

## Context

The search pipeline consists of three stages: MegaLoc retrieval (fast, <1s), MASt3R dense matching (slow, 2-4 minutes for 500 candidates), and spatial consensus (<1s). The original Tkinter code ran everything in a background thread with a polling queue for UI updates. In the web-based architecture, we need a clean async execution model that:

1. Does not block the FastAPI event loop.
2. Provides real-time progress updates to the Web UI.
3. Supports cancellation mid-search.
4. Allows multiple concurrent searches.

## Decision

### 1. PipelineController Location

Place `PipelineController` in **`core/pipeline.py`**. It is the sole orchestrator for executing all three pipeline stages. It is NOT part of any engine — it selects an engine at search time and delegates Stage 2 execution to it.

### 2. Async Job Model

```
POST /api/v1/search/run
  -> Validate inputs
  -> Generate job_id (uuid4)
  -> Store job metadata in in-memory dict (jobs[job_id] = {status, progress, result, cancel_event})
  -> Spawn background thread via asyncio.get_event_loop().run_in_executor()
  -> Return 202 Accepted { "job_id": "uuid", "status": "queued" }

WS /api/v1/ws/search?job_id=<uuid>
  -> Client connects
  -> Server subscribes to job_id's update channel
  -> On each pipeline stage change: push JSON message
  -> Client can send { "type": "cancel" } to trigger cancel_event

GET /api/v1/search/status/<job_id>
  -> Returns current job state for HTTP-polling clients
```

### 3. Job State Machine

```
queued -> running -> complete | failed | cancelled
```

States:
- `queued`: job created, not yet started
- `running`: pipeline executing
- `complete`: all stages finished, result available
- `failed`: unrecoverable error (model load failure, OOM)
- `cancelled`: user requested cancellation

### 4. WebSocket Message Protocol

**Server -> Client:**

```json
{"type": "status", "message": "Loading index...", "job_id": "uuid"}
{"type": "progress", "phase": "retrieval", "current": 0, "total": 0, "job_id": "uuid"}
{"type": "progress", "phase": "matching", "current": 42, "total": 500, "job_id": "uuid"}
{"type": "match_update", "lat": 55.7558, "lon": 37.6173, "inliers": 320, "heading": 180, "current": 42, "total": 500}
{"type": "complete", "result": {"lat": 55.7558, "lon": 37.6173, "inliers": 452}, "candidates": [...], "job_id": "uuid"}
{"type": "error", "message": "MASt3R model failed to load", "job_id": "uuid"}
```

**Client -> Server:**

```json
{"type": "cancel"}
```

### 5. Concurrency Model

- A `ThreadPoolExecutor` with `max_workers=1` for GPU-bound searches (prevents VRAM contention).
- A `ThreadPoolExecutor` with `max_workers=2` for CPU-bound searches.
- If a second search is requested while the GPU is busy, it is queued with status `queued`.
- When the active search finishes, the next queued job begins automatically.

### 6. Cancellation

Each job has a `threading.Event()` named `cancel_event`. The Stage 2 candidate loop checks `cancel_event.is_set()` before processing each candidate. When cancelled mid-iteration, the current result up to that point is still saved and returned so the user sees partial progress.

## Consequences

- (+) Eliminates HTTP timeouts — search runs entirely in background.
- (+) Real-time progress bar and candidate match display in Web UI.
- (+) Multiple search jobs can be queued.
- (+) Cancellation returns partial results rather than discarding everything.
- (-) Increases implementation complexity — need job lifecycle management, WebSocket connection tracking, and cleanup for stale jobs.
- (-) In-memory job storage means jobs are lost on server restart (acceptable for a local tool).

## Alternatives Considered

| Alternative | Why Rejected |
|---|---|
| Celery + Redis | Overkill for a local desktop tool. Adds Redis dependency. |
| Sync HTTP with 5-min timeout | Browsers/Hardware load balancers typically timeout at 30-120s. 4-min MASt3R would still fail. |
| Server-Sent Events (SSE) over WebSocket | SSE is unidirectional (server->client); we need client->server cancel. WebSocket is bidirectional. |
