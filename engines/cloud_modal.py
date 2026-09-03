import io
import logging
import os
import threading
import time
from collections.abc import Callable
from typing import Any

import requests
import numpy as np
from PIL import Image

from config import MATCHING_TOP_K, MODAL_WORKER_URL
from engines.base import EngineBase

log = logging.getLogger("netryx.engine.cloud")

_MODAL_TOKEN_ID = os.environ.get("MODAL_TOKEN_ID")
_MODAL_TOKEN_SECRET = os.environ.get("MODAL_TOKEN_SECRET")
_DEFAULT_ENDPOINT = MODAL_WORKER_URL


class CloudModalEngine(EngineBase):
    def __init__(
        self,
        endpoint_url: str = _DEFAULT_ENDPOINT,
        token_id: str | None = _MODAL_TOKEN_ID,
        token_secret: str | None = _MODAL_TOKEN_SECRET,
    ) -> None:
        self._endpoint = endpoint_url.rstrip("/")
        self._auth = (token_id, token_secret) if token_id and token_secret else None
        try:
            import torch
            self._device = torch.device("cpu")
        except ImportError:
            self._device = "cpu"  # type: ignore[assignment]
        log.info("CloudModalEngine -> %s", self._endpoint)

    @property
    def device(self) -> Any:
        return self._device

    @staticmethod
    def available() -> bool:
        return bool(_DEFAULT_ENDPOINT or (_MODAL_TOKEN_ID and _MODAL_TOKEN_SECRET))

    def run_stage2(
        self,
        query_img: Image.Image,
        candidates: list[dict],
        crop_fov: int = 90,
        crop_size: int = 256,
        early_exit_threshold: int = 450,
        cancel_event: threading.Event | None = None,
        progress_callback: Callable | None = None,
        match_collector: list | None = None,
    ) -> dict:
        buf = io.BytesIO()
        query_img.save(buf, format="JPEG", quality=85)
        query_bytes = buf.getvalue()

        all_matches: list[dict] = []
        best: dict = {"inliers": 0, "panoid": None}

        candidates_to_check = candidates[:MATCHING_TOP_K]
        for i, match in enumerate(candidates_to_check):
            if cancel_event and cancel_event.is_set():
                log.info("Cloud stage 2 cancelled at %d/%d", i, len(candidates_to_check))
                break

            if progress_callback:
                progress_callback(i, len(candidates_to_check))

            pid = match.get("panoid")
            hdg = match.get("heading")
            if not pid or hdg is None:
                continue

            result = self._call_worker(
                query_bytes=query_bytes,
                panoid=pid,
                heading=hdg,
                lat=match.get("lat", 0.0),
                lon=match.get("lon", 0.0),
                crop_fov=crop_fov,
                crop_size=crop_size,
            )

            score = result.get("inliers", 0)
            if score > 50:
                entry = {
                    "inliers": score,
                    "panoid": pid,
                    "heading": hdg,
                    "lat": match.get("lat"),
                    "lon": match.get("lon"),
                }
                all_matches.append(entry)
                if match_collector is not None:
                    match_collector.append(entry)

            if score > best["inliers"]:
                best = {
                    "inliers": score,
                    "panoid": pid,
                    "heading": hdg,
                    "lat": match.get("lat"),
                    "lon": match.get("lon"),
                }
                if score >= early_exit_threshold:
                    log.info("Cloud early exit at %d inliers", score)
                    break

        return self._build_result(best, all_matches, candidates)

    def _call_worker(
        self,
        query_bytes: bytes,
        panoid: str,
        heading: int,
        lat: float,
        lon: float,
        crop_fov: int = 90,
        crop_size: int = 256,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        last_error: str | None = None
        for attempt in range(max_retries):
            try:
                files = {"query": ("query.jpg", query_bytes, "image/jpeg")}
                data = {
                    "panoid": panoid,
                    "heading": heading,
                    "lat": lat,
                    "lon": lon,
                    "crop_fov": crop_fov,
                    "crop_size": crop_size,
                }
                resp = requests.post(
                    f"{self._endpoint}/match",
                    files=files,
                    data=data,
                    auth=self._auth,
                    timeout=120,
                )
                if resp.status_code == 200:
                    return resp.json()
                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            except requests.RequestException as e:
                last_error = str(e)

            if attempt < max_retries - 1:
                backoff = 2 ** attempt
                log.warning("Retry %d/%d for %s in %ds: %s", attempt + 1, max_retries, panoid, backoff, last_error)
                time.sleep(backoff)

        log.error("Worker call failed for %s after %d retries: %s", panoid, max_retries, last_error)
        return {"inliers": 0, "error": last_error, "panoid": panoid}

    def _build_result(self, best: dict, all_matches: list[dict], candidates: list[dict]) -> dict:
        if best["inliers"] > 0:
            best["inliers"] = 200 + best["inliers"] // 10
        return {
            "best": best,
            "all_matches": all_matches,
            "total_candidates": len(candidates[:MATCHING_TOP_K]),
        }

    def search_index(
        self,
        query_np: Any,
        center: tuple[float, float],
        radius_km: float,
        top_k: int = 1000,
        repo_name: str | None = None,
    ) -> list[dict[str, Any]]:
        try:
            data: dict[str, Any] = {
                "lat": center[0],
                "lon": center[1],
                "radius": radius_km,
                "top_k": top_k,
            }
            if repo_name:
                data["repo_name"] = repo_name

            files = None
            if query_np is not None:
                if isinstance(query_np, np.ndarray):
                    vec = query_np.flatten().astype(np.float32)
                    if len(vec) == 1024:
                        qbytes = vec.tobytes()
                        files = {"query": ("query.bin", qbytes, "application/octet-stream")}
                    else:
                        try:
                            qimg = Image.fromarray(query_np.astype(np.uint8))
                            buf = io.BytesIO()
                            qimg.save(buf, format="JPEG", quality=85)
                            files = {"query": ("query.jpg", buf.getvalue(), "image/jpeg")}
                        except Exception:
                            qbytes = np.zeros((1024,), dtype=np.float32).tobytes()
                            files = {"query": ("query.bin", qbytes, "application/octet-stream")}
                elif isinstance(query_np, (bytes, bytearray)):
                    files = {"query": ("query.bin", bytes(query_np), "application/octet-stream")}
                elif isinstance(query_np, Image.Image):
                    buf = io.BytesIO()
                    query_np.save(buf, format="JPEG", quality=85)
                    files = {"query": ("query.jpg", buf.getvalue(), "image/jpeg")}

            if files is None:
                qbytes = np.zeros((1024,), dtype=np.float32).tobytes()
                files = {"query": ("query.bin", qbytes, "application/octet-stream")}

            resp = requests.post(
                f"{self._endpoint}/search",
                data=data,
                files=files,
                auth=self._auth,
                timeout=120,
            )
            if resp.status_code == 200:
                res = resp.json()
                return res.get("candidates", [])
            log.error("Modal /search error HTTP %d: %s", resp.status_code, resp.text[:200])
            return []
        except Exception as e:
            log.exception("CloudModalEngine search_index failed: %s", e)
            return []

    def get_index_info(self) -> dict[str, Any]:
        try:
            resp = requests.get(f"{self._endpoint}/index/info", auth=self._auth, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            return {"loaded": False, "entries": 0}
        except Exception as e:
            log.warning("Modal /index/info failed: %s", e)
            return {"loaded": False, "entries": 0}

    def download_hub_index(self, repo_name: str) -> dict[str, Any]:
        try:
            resp = requests.post(
                f"{self._endpoint}/index/hub/download",
                data={"repo_name": repo_name},
                auth=self._auth,
                timeout=300,
            )
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        except Exception as e:
            log.exception("Modal /index/hub/download failed: %s", e)
            return {"error": str(e)}

    def upload_index(self, file_bytes: bytes, filename: str) -> dict[str, Any]:
        try:
            files = {"file": (filename, file_bytes, "application/octet-stream")}
            resp = requests.post(
                f"{self._endpoint}/index/load",
                files=files,
                auth=self._auth,
                timeout=300,
            )
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        except Exception as e:
            log.exception("Modal /index/load failed: %s", e)
            return {"error": str(e)}

    def get_index_coverage(self) -> dict[str, Any]:
        try:
            resp = requests.get(f"{self._endpoint}/index/coverage", auth=self._auth, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            return {"type": "FeatureCollection", "features": []}
        except Exception as e:
            log.warning("Modal /index/coverage failed: %s", e)
            return {"type": "FeatureCollection", "features": []}

    def unload_models(self) -> None:
        log.info("CloudModalEngine: no local models to unload")
