import logging
from typing import Any

from engines.cloud_modal import CloudModalEngine
from engines.local_cpu import LocalCPUEngine
from engines.local_gpu import LocalGPUEngine

log = logging.getLogger("netryx.engine")


def auto_detect_engine(prefer: str = "auto") -> Any:
    if prefer == "cloud" and CloudModalEngine.available():
        log.info("Selected CloudModalEngine")
        return CloudModalEngine()

    try:
        import torch
        has_cuda = torch.cuda.is_available()
        has_mps = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
    except ImportError:
        has_cuda = False
        has_mps = False

    if prefer == "gpu" or (prefer == "auto" and has_cuda):
        log.info("Auto-selected LocalGPUEngine")
        return LocalGPUEngine("cuda")
    if prefer == "mps" or (prefer == "auto" and has_mps):
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
