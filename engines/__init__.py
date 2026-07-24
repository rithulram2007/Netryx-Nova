import logging
from typing import Any

import torch

from engines.local_cpu import LocalCPUEngine
from engines.local_gpu import LocalGPUEngine

log = logging.getLogger("netryx.engine")


def auto_detect_engine(prefer: str = "auto") -> Any:
    if prefer == "gpu" or (prefer == "auto" and torch.cuda.is_available()):
        log.info("Auto-selected LocalGPUEngine")
        return LocalGPUEngine("cuda")
    if prefer == "mps" or (prefer == "auto" and torch.backends.mps.is_available()):
        log.info("Auto-selected LocalGPUEngine (MPS)")
        return LocalGPUEngine("mps")
    log.info("Auto-selected LocalCPUEngine")
    return LocalCPUEngine()