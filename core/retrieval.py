import logging
from typing import Any

import numpy as np

from config import COMPACT_INDEX_DIR, RETRIEVAL_TOP_K
from core.exceptions import IndexNotFoundError
from utils.netryx_loader import build_faiss_index, load_compact_index

log = logging.getLogger("netryx.retrieval")

_index_instance: Any = None
_metadata_instance: dict[str, Any] | None = None
_index_dir_loaded: str | None = None
_use_faiss: bool = True


def load_or_build_index(
    index_dir: str | None = None,
    use_faiss: bool = True,
    force_reload: bool = False,
) -> tuple[Any, dict[str, Any]]:
    global _index_instance, _metadata_instance, _index_dir_loaded, _use_faiss

    target_dir = index_dir or COMPACT_INDEX_DIR

    if not force_reload and _index_instance is not None and _index_dir_loaded == target_dir:
        assert _metadata_instance is not None
        return _index_instance, _metadata_instance

    descs, metadata = load_compact_index(target_dir)
    if descs is None or metadata is None:
        raise IndexNotFoundError(f"No index found at {target_dir}")
    assert metadata is not None

    if use_faiss:
        try:
            _index_instance = build_faiss_index(descs)
            _use_faiss = True
            log.info("Using FAISS index for search")
        except ImportError:
            log.warning("FAISS not available, falling back to numpy chunked search")
            _use_faiss = False
            _index_instance = descs
    else:
        _use_faiss = False
        _index_instance = descs

    _metadata_instance = metadata
    _index_dir_loaded = target_dir
    return _index_instance, _metadata_instance


def reset_index() -> None:
    global _index_instance, _metadata_instance, _index_dir_loaded
    _index_instance = None
    _metadata_instance = None
    _index_dir_loaded = None
    log.info("Index singleton reset")


def search_index(
    query_desc: np.ndarray,
    center: tuple[float, float],
    radius_km: float,
    top_k: int = RETRIEVAL_TOP_K,
    index_dir: str | None = None,
) -> list[dict[str, Any]]:
    index, metadata = load_or_build_index(index_dir=index_dir)

    lat1 = np.radians(center[0])
    lon1 = np.radians(center[1])
    lat2 = np.radians(metadata["lats"])
    lon2 = np.radians(metadata["lons"])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    distances = 6371 * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    radius_mask = distances <= radius_km
    radius_indices = np.where(radius_mask)[0]

    n_in_radius = len(radius_indices)
    log.info("Radius filter: %d/%d in %.1fkm", n_in_radius, len(metadata["lats"]), radius_km)
    if n_in_radius == 0:
        return []

    query_norm = query_desc / (np.linalg.norm(query_desc) + 1e-8)
    query_norm = query_norm.astype(np.float32).reshape(1, -1)

    if _use_faiss:
        top_scores_arr = np.full(top_k, -np.inf, dtype=np.float32)
        top_indices_arr = np.zeros(top_k, dtype=np.int64)

        for chunk_start in range(0, n_in_radius, 100_000):
            chunk_end = min(chunk_start + 100_000, n_in_radius)
            chunk_idx = radius_indices[chunk_start:chunk_end]
            chunk_scores = index.reconstruct_n(int(chunk_idx[0]), len(chunk_idx)) @ query_norm.T
            chunk_scores = chunk_scores.flatten()

            combined_scores = np.concatenate([top_scores_arr, chunk_scores])
            combined_indices = np.concatenate([top_indices_arr, chunk_idx])
            k = min(top_k, len(combined_scores))
            best_k = np.argsort(combined_scores)[::-1][:k]
            top_scores_arr = combined_scores[best_k]
            top_indices_arr = combined_indices[best_k]
    else:
        descs = index
        chunk_size = 100_000
        top_scores_arr = np.full(top_k, -np.inf, dtype=np.float32)
        top_indices_arr = np.zeros(top_k, dtype=np.int64)

        for chunk_start in range(0, n_in_radius, chunk_size):
            chunk_end = min(chunk_start + chunk_size, n_in_radius)
            chunk_idx = radius_indices[chunk_start:chunk_end]
            chunk_descs = np.array(descs[chunk_idx], dtype=np.float32)
            chunk_sims = chunk_descs @ query_norm.flatten()
            del chunk_descs

            combined_scores = np.concatenate([top_scores_arr, chunk_sims])
            combined_indices = np.concatenate([top_indices_arr, chunk_idx])
            k = min(top_k, len(combined_scores))
            best_k = np.argsort(combined_scores)[::-1][:k]
            top_scores_arr = combined_scores[best_k]
            top_indices_arr = combined_indices[best_k]

    seen_panoids: dict[str, dict[str, Any]] = {}
    for gi, score in zip(top_indices_arr, top_scores_arr):
        if score == -np.inf:
            break
        pid = str(metadata["panoids"][gi])
        if pid not in seen_panoids or score > seen_panoids[pid]["score"]:
            seen_panoids[pid] = {
                "panoid": pid,
                "heading": int(metadata["headings"][gi]),
                "lat": float(metadata["lats"][gi]),
                "lon": float(metadata["lons"][gi]),
                "score": float(score),
                "path": str(metadata["paths"][gi]),
            }

    results = sorted(seen_panoids.values(), key=lambda x: x["score"], reverse=True)[:top_k]
    log.info("Search: top-%d unique panoids (best: %.3f)", len(results), results[0]["score"] if results else 0)
    return results
