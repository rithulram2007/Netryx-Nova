# Task 01: Async Job Model & PipelineController

## Target Files

- `core/pipeline.py` (new)
- `tests/test_pipeline.py` (new)

## Description

Implement the PipelineController that manages the async job lifecycle: job creation, background execution via ThreadPoolExecutor, WebSocket progress streaming, cancellation, and cleanup of stale jobs.

## Checklist

- [ ] Define `SearchJob` dataclass: job_id, status, progress, cancel_event, engine, result
- [ ] Implement `PipelineController` class:
  - `create_job(image, lat, lon, radius, engine_mode) -> SearchJob`
  - `start_job(job_id)` — spawns background thread
  - `cancel_job(job_id)` — sets cancel_event
  - `get_job(job_id) -> SearchJob`
  - `cleanup_stale_jobs()` — removes jobs older than JOB_CLEANUP_TIMEOUT
  - `_run_pipeline(job)` — orchestrates stages 1-3
- [ ] Implement engine selection: auto-detect (CUDA -> Modal -> CPU) or manual override
- [ ] Implement VRAM management: `unload_models()` on engine switch
- [ ] Implement WebSocket message bridge (queue-based)
- [ ] Implement cancel checking in Stage 2 candidate loop
- [ ] Implement partial result on cancel (save best match so far)
- [ ] Add ThreadPoolExecutor with max_workers=1 for GPU, 2 for CPU
- [ ] Thread safety: Lock around jobs dict for concurrent access

## Verification

```bash
pytest tests/test_pipeline.py -v
```
