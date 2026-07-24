import gc
import logging
import threading
from abc import ABC, abstractmethod
from typing import Any

import torch
from PIL import Image

log = logging.getLogger("netryx.engine")


class EngineBase(ABC):

    @property
    @abstractmethod
    def device(self) -> torch.device:
        ...

    @abstractmethod
    def run_stage2(
        self,
        query_img: Image.Image,
        candidates: list[dict],
        crop_fov: int = 90,
        crop_size: int = 256,
        early_exit_threshold: int = 450,
        cancel_event: threading.Event | None = None,
        progress_callback: Any = None,
        match_collector: list | None = None,
    ) -> dict:
        ...

    def unload_models(self) -> None:
        self._unload_mast3r()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
        gc.collect()
        log.info("Engine models unloaded, VRAM cleared")

    def _unload_mast3r(self) -> None:
        import mast3r_utils
        mast3r_utils._mast3r_model = None
