import logging
from typing import Any

import numpy as np
import torch
from PIL import Image

import mast3r_utils
from mast3r_utils import get_mast3r_matches, get_mast3r_model

log = logging.getLogger("netryx.matching")

_model_instance: Any = None


def get_lazy_mast3r(device: torch.device | None = None) -> Any:
    global _model_instance
    if _model_instance is None:
        _model_instance = get_mast3r_model()
    return _model_instance


def reset_model() -> None:
    global _model_instance
    _model_instance = None
    mast3r_utils._mast3r_model = None
    log.info("MASt3R model reference cleared")


def compute_matches(
    query_pil: Image.Image,
    candidate_pil: Image.Image,
    model: Any | None = None,
) -> tuple[np.ndarray, np.ndarray, None]:
    if model is None:
        model = get_lazy_mast3r()
    if model is None:
        return np.array([]), np.array([]), None
    return get_mast3r_matches(query_pil, candidate_pil, model)
