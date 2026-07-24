# Feature: Pipeline Controller & Asynchronous Execution

## Overview

The PipelineController (`core/pipeline.py`) is the central orchestrator that coordinates all three pipeline stages, manages the async job lifecycle, and streams progress to clients via WebSocket. It is the bridge between the FastAPI web layer and the core/engines modules.

## Business Logic

1. **Job Creation**: `POST /api/v1/search/run` creates a job with `uuid4` and returns `202 Accepted` immediately.
2. **Stage Execution**: A background thread runs stages sequentially through the pipeline controller.
3. **Progress Streaming**: Each stage pushes updates to an in-memory queue; a WebSocket consumer reads from the queue and forwards to the connected client.
4. **Cancellation**: Client sends `{"type": "cancel"}` via WebSocket. The controller sets a `threading.Event()` checked at each candidate iteration.
5. **Engine Selection**: At job start, the controller selects the appropriate engine (auto-detect or manual override) and caches the selection for that job's lifetime.
6. **VRAM Management**: When switching engines between jobs (e.g., finishing GPU job then starting CPU job), the controller calls `engine.unload_models()` on the previous job's engine.

## Job State Machine

```
queued -> running -> complete | failed | cancelled
```

## Key Config (config.py)

```python
MAX_CONCURRENT_GPU_JOBS = 1
MAX_CONCURRENT_CPU_JOBS = 2
JOB_CLEANUP_TIMEOUT_SECONDS = 300  # Remove stale job state after 5 min
```

## Key Files

| File | Purpose |
|---|---|
| `core/pipeline.py` | PipelineController: orchestrator, job lifecycle, WS bridge |
| `ui/static/js/app.js` | WebSocket client, job state machine, status display |
| `ui/web_app.py` | Route definitions for search endpoints + WebSocket handler |

## Dependencies

- `asyncio` / `concurrent.futures` for background thread pool
- `uuid` for job IDs
- `websockets` (via FastAPI/Starlette) for WS handling

## Verification

```bash
# Start server, then:
curl -X POST -F "image=@test.jpg" -F "lat=55.75" -F "lon=37.62" http://localhost:8000/api/v1/search/run
# Returns {"job_id": "...", "status": "queued"}
```
