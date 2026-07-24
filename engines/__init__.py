import logging
from typing import Any

import torch

from engines.cloud_modal import CloudModalEngine
from engines.local_cpu import LocalCPUEngine
from engines.local_gpu import LocalGPUEngine

log = logging.getLogger("netryx.engine")


def auto_detect_engine(prefer: str = "auto") -> Any:
    if prefer == "cloud" and CloudModalEngine.available():
        log.info("Selected CloudModalEngine")
        return CloudModalEngine()

    if prefer == "gpu" or (prefer == "auto" and torch.cuda.is_available()):
        log.info("Auto-selected LocalGPUEngine")
        return LocalGPUEngine("cuda")
    if prefer == "mps" or (prefer == "auto" and torch.backends.mps.is_available()):
        log.info("Auto-selected LocalGPUEngine (MPS)")
        return LocalGPUEngine("mps")

    if prefer == "auto" and CloudModalEngine.available():
        log.info("Auto-selected CloudModalEngine (fallback after GPU)")
        return CloudModalEngine()

    if prefer == "cloud":
        log.warning("CloudModalEngine selected but no credentials found, falling back to CPU")
        return LocalCPUEngine()

    log.info("Auto-selected LocalCPUEngine")
    return LocalCPUEngine()
