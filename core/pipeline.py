import logging
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from PIL import Image

from config import (
    JOB_CLEANUP_TIMEOUT_SECONDS,
    MATCHING_TOP_K,
    MAX_CONCURRENT_CPU_JOBS,
    MAX_CONCURRENT_GPU_JOBS,
    RETRIEVAL_TOP_K,
)
from core.consensus import spatial_consensus
from core.exceptions import IndexNotFoundError
from core.retrieval import search_index
from engines import auto_detect_engine
from engines.base import EngineBase
from engines.local_cpu import LocalCPUEngine
from engines.local_gpu import LocalGPUEngine

log = logging.getLogger("netryx.pipeline")


@dataclass
class JobState:
    job_id: str
    status: str = "queued"
    cancel_event: threading.Event = field(default_factory=threading.Event)
    progress_queue: queue.Queue = field(default_factory=queue.Queue)
    result: dict | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    engine_prefer: str = "auto"
    lat: float = 0.0
    lon: float = 0.0
    radius_km: float = 0.5


class PipelineController:
    def __init__(self) -> None:
        self._jobs: dict[str, JobState] = {}
        self._lock = threading.Lock()
        self._current_engine: EngineBase | None = None
        self._current_engine_type: str | None = None
        self._gpu_job_count = 0
        self._cpu_job_count = 0
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()

    def create_job(
        self,
        query_img: Image.Image,
        lat: float,
        lon: float,
        radius_km: float = 0.5,
        engine_prefer: str = "auto",
        index_dir: str | None = None,
    ) -> str:
        job_id = str(uuid.uuid4())
        state = JobState(
            job_id=job_id,
            engine_prefer=engine_prefer,
            lat=lat,
            lon=lon,
            radius_km=radius_km,
        )
        with self._lock:
            self._jobs[job_id] = state

        thread = threading.Thread(
            target=self._run_job,
            args=(job_id, query_img, index_dir),
            daemon=True,
        )
        thread.start()
        log.info("Job %s created (engine=%s)", job_id, engine_prefer)
        return job_id

    def cancel_job(self, job_id: str) -> bool:
        with self._lock:
            state = self._jobs.get(job_id)
            if state is None or state.status in ("complete", "failed", "cancelled"):
                return False
            state.cancel_event.set()
            state.status = "cancelled"
            state.finished_at = time.time()
            state.progress_queue.put({"type": "status", "message": "Job cancelled"})
        self._release_engine_slot(state)
        log.info("Job %s cancelled", job_id)
        return True

    def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            state = self._jobs.get(job_id)
            if state is None:
                return None
            messages: list[dict[str, Any]] = []
            while not state.progress_queue.empty():
                try:
                    messages.append(state.progress_queue.get_nowait())
                except queue.Empty:
                    break
            info: dict[str, Any] = {
                "job_id": state.job_id,
                "status": state.status,
                "error": state.error,
                "progress_messages": messages,
            }
            if state.result is not None:
                info["result"] = state.result
            return info

    def set_engine(self, engine_type: str, workspace: str | None = None) -> EngineBase:
        if self._current_engine is not None and self._current_engine_type != engine_type:
            self._current_engine.unload_models()
            gc_imported = __import__("gc")
            gc_imported.collect()
            self._current_engine = None
            self._current_engine_type = None

        if self._current_engine is not None:
            return self._current_engine

        if engine_type in ("gpu", "cuda"):
            self._current_engine = LocalGPUEngine("cuda")
        elif engine_type == "mps":
            self._current_engine = LocalGPUEngine("mps")
        elif engine_type == "cpu":
            self._current_engine = LocalCPUEngine()
        else:
            self._current_engine = auto_detect_engine()

        self._current_engine_type = engine_type
        log.info("Engine set to %s", type(self._current_engine).__name__)
        return self._current_engine

    def _run_job(
        self,
        job_id: str,
        query_img: Image.Image,
        index_dir: str | None = None,
    ) -> None:
        state = self._get_state(job_id)
        if state is None:
            return

        if not self._acquire_engine_slot(state):
            return

        try:
            state.status = "running"
            state.progress_queue.put({
                "type": "status",
                "stage": 1,
                "message": "Stage 1: Retrieving candidates",
            })

            query_np = np.array(query_img, dtype=np.float32)
            candidates = search_index(
                query_desc=query_np,
                center=(state.lat, state.lon),
                radius_km=state.radius_km,
                top_k=RETRIEVAL_TOP_K,
                index_dir=index_dir,
            )

            state.progress_queue.put({
                "type": "status",
                "stage": 1,
                "message": f"Stage 1 complete — {len(candidates)} candidates",
                "progress": {"current": 0, "total": len(candidates[:MATCHING_TOP_K])},
                "candidates": candidates[:MATCHING_TOP_K],
            })

            if state.cancel_event.is_set():
                return

            if not candidates:
                state.status = "complete"
                state.result = {"best": {"inliers": 0}, "all_matches": [], "top_clusters": []}
                state.progress_queue.put({
                    "type": "complete",
                    "result": state.result,
                    "message": "No candidates found in search radius",
                })
                return

            engine = self.set_engine(state.engine_prefer, index_dir)

            match_collector: list[dict] = []

            def progress_cb(current: int, total: int) -> None:
                state.progress_queue.put({
                    "type": "progress",
                    "current": current,
                    "total": total,
                })

            result = engine.run_stage2(
                query_img=query_img,
                candidates=candidates,
                cancel_event=state.cancel_event,
                progress_callback=progress_cb,
                match_collector=match_collector,
            )

            if state.cancel_event.is_set():
                return

            all_matches = match_collector or result.get("all_matches", [])
            state.progress_queue.put({
                "type": "status",
                "stage": 2,
                "message": f"Stage 2 complete — {len(all_matches)} matches",
                "total_candidates": len(candidates[:MATCHING_TOP_K]),
            })

            top_clusters = spatial_consensus(all_matches)

            state.result = {
                "best": result.get("best", {"inliers": 0}),
                "all_matches": all_matches,
                "top_clusters": top_clusters,
            }
            state.status = "complete"
            state.progress_queue.put({
                "type": "complete",
                "result": state.result,
                "top_clusters": top_clusters,
            })
            log.info("Job %s complete — %d clusters", job_id, len(top_clusters))

        except IndexNotFoundError:
            state.status = "failed"
            state.error = "Index not found. Load a .netryx bundle first."
            state.progress_queue.put({"type": "error", "message": state.error})
        except Exception as e:
            log.exception("Job %s failed", job_id)
            state.status = "failed"
            state.error = str(e)
            state.progress_queue.put({"type": "error", "message": str(e)})
        finally:
            state.finished_at = time.time()
            self._release_engine_slot(state)

    def _acquire_engine_slot(self, state: JobState) -> bool:
        max_jobs = MAX_CONCURRENT_GPU_JOBS if state.engine_prefer in ("gpu", "cuda", "mps") else MAX_CONCURRENT_CPU_JOBS
        deadline = time.time() + 60
        while time.time() < deadline:
            with self._lock:
                if state.engine_prefer in ("gpu", "cuda", "mps"):
                    if self._gpu_job_count < max_jobs:
                        self._gpu_job_count += 1
                        return True
                else:
                    if self._cpu_job_count < max_jobs:
                        self._cpu_job_count += 1
                        return True
            time.sleep(0.5)

        state.status = "failed"
        state.error = f"No available {state.engine_prefer} slot after 60s"
        state.progress_queue.put({"type": "error", "message": state.error})
        return False

    def _release_engine_slot(self, state: JobState) -> None:
        with self._lock:
            if state.engine_prefer in ("gpu", "cuda", "mps"):
                self._gpu_job_count = max(0, self._gpu_job_count - 1)
            else:
                self._cpu_job_count = max(0, self._cpu_job_count - 1)

    def _get_state(self, job_id: str) -> JobState | None:
        with self._lock:
            return self._jobs.get(job_id)

    def _cleanup_loop(self) -> None:
        while True:
            time.sleep(30)
            now = time.time()
            with self._lock:
                stale = [
                    jid
                    for jid, s in self._jobs.items()
                    if s.status in ("complete", "failed", "cancelled")
                    and s.finished_at is not None
                    and (now - s.finished_at) > JOB_CLEANUP_TIMEOUT_SECONDS
                ]
                for jid in stale:
                    del self._jobs[jid]
                if stale:
                    log.debug("Cleaned %d stale jobs", len(stale))

    @property
    def active_jobs(self) -> int:
        with self._lock:
            return sum(1 for s in self._jobs.values() if s.status == "running")
