import gc
import logging
import threading
from collections.abc import Callable
from typing import Any

try:
    import torch
except ImportError:
    torch = None  # type: ignore[assignment]
from PIL import Image

from config import MATCHING_TOP_K
from core.matching import compute_matches, get_lazy_mast3r, reset_model
from engines.base import EngineBase
from utils.geo_utils import (
    equirectangular_to_rectilinear_torch,
    get_projection_base_dirs,
    pil_to_tensor,
    tensor_to_pil,
)
from utils.tile_downloader import download_tiles, stitch_tiles, tiles_info

log = logging.getLogger("netryx.engine.gpu")


def _device_str() -> str:
    if torch is not None and hasattr(torch, "cuda") and torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _empty_cache() -> None:
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()


class LocalGPUEngine(EngineBase):
    def __init__(self, device_str: str | None = None) -> None:
        self._device_str = device_str or _device_str()
        self._device = torch.device(self._device_str)
        log.info("GPU engine initialized on %s", self._device_str)

    @property
    def device(self) -> Any:
        return self._device

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
        mast3r = get_lazy_mast3r(self._device)
        if mast3r is None:
            return {"inliers": 0}

        query_img_resize = query_img.resize((crop_size, crop_size), Image.BILINEAR)
        base_dirs = get_projection_base_dirs(float(crop_fov), (crop_size, crop_size), self._device)

        all_matches: list[dict] = []
        best: dict = {"inliers": 0, "panoid": None}

        candidates_to_check = candidates[:MATCHING_TOP_K]
        for i, match in enumerate(candidates_to_check):
            if cancel_event and cancel_event.is_set():
                log.info("Stage 2 cancelled at candidate %d/%d", i, len(candidates_to_check))
                break

            if progress_callback:
                progress_callback(i, len(candidates_to_check))

            pid = match.get("panoid")
            hdg = match.get("heading")
            if not pid or hdg is None:
                continue

            pano_img = None
            try:
                tiles = tiles_info(pid)
                td = download_tiles(tiles, max_workers=16)
                if td:
                    pano_img = stitch_tiles(td)
                    maxw = 2048
                    if pano_img.size[0] > maxw:
                        ratio = maxw / pano_img.size[0]
                        pano_img = pano_img.resize((maxw, int(pano_img.size[1] * ratio)), Image.BILINEAR)
            except Exception:
                continue

            if pano_img is None:
                continue

            try:
                pano_t = pil_to_tensor(pano_img, self._device)
                crop_t = equirectangular_to_rectilinear_torch(
                    pano_t, fov_deg=float(crop_fov), out_hw=(crop_size, crop_size),
                    yaw_deg=[hdg], pitch_deg=0, base_dirs=base_dirs,
                )[0].unsqueeze(0)
                crop_pil = tensor_to_pil(crop_t)
                m0, m1, _ = compute_matches(query_img_resize, crop_pil, mast3r)
                score = len(m0)

                if score > 50:
                    match_entry = {
                        "inliers": score,
                        "panoid": pid,
                        "heading": hdg,
                        "lat": match.get("lat"),
                        "lon": match.get("lon"),
                        "kp1": m0,
                        "kp2": m1,
                    }
                    all_matches.append(match_entry)
                    if match_collector is not None:
                        match_collector.append(match_entry)

                if score > best["inliers"]:
                    best = {
                        "inliers": score,
                        "panoid": pid,
                        "heading": hdg,
                        "lat": match.get("lat"),
                        "lon": match.get("lon"),
                        "kp1": m0,
                        "kp2": m1,
                    }
                    if score >= early_exit_threshold:
                        log.info("Early exit at %d inliers", score)
                        return self._build_result(best, all_matches, candidates)

                del pano_t, crop_t
                pano_img.close()
                _empty_cache()

            except Exception as e:
                log.debug("Candidate %s failed: %s", pid, e)
                continue

        return self._build_result(best, all_matches, candidates)

    def _build_result(self, best: dict, all_matches: list[dict], candidates: list[dict]) -> dict:
        if best["inliers"] > 0:
            best["inliers"] = 200 + best["inliers"] // 10
        return {
            "best": best,
            "all_matches": all_matches,
            "total_candidates": len(candidates[:MATCHING_TOP_K]),
        }

    def unload_models(self) -> None:
        reset_model()
        _empty_cache()
        gc.collect()
        log.info("GPU engine models unloaded")
