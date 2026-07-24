import json
import logging
import os
import zipfile
from typing import Any

import numpy as np

from config import COMPACT_DESCS_PATH, COMPACT_META_PATH

log = logging.getLogger("netryx.loader")


def parse_emb_path(emb_path: str) -> tuple[str | None, int | None]:
    filename = os.path.basename(emb_path)
    name = filename.replace(".npz", "")
    parts = name.rsplit("_", 1)
    if len(parts) == 2:
        try:
            return parts[0], int(parts[1])
        except ValueError:
            pass
    return None, None


def load_compact_index(
    index_dir: str | None = None,
) -> tuple[np.ndarray | None, dict[str, Any] | None]:
    descs_path = os.path.join(index_dir, "megaloc_descriptors.npy") if index_dir else COMPACT_DESCS_PATH
    meta_path = os.path.join(index_dir, "metadata.npz") if index_dir else COMPACT_META_PATH

    if not os.path.exists(descs_path) or not os.path.exists(meta_path):
        log.error("Compact index not found at %s", descs_path)
        return None, None

    log.info("Loading compact index (memory-mapped)...")
    descs = np.load(descs_path, mmap_mode="r")
    meta = np.load(meta_path, allow_pickle=True)
    metadata: dict[str, Any] = {
        "lats": meta["lats"].copy(),
        "lons": meta["lons"].copy(),
        "headings": meta["headings"].copy(),
        "panoids": meta["panoids"],
        "paths": meta["paths"],
    }
    log.info("Loaded %d entries (%d-dim)", len(descs), descs.shape[1])
    return descs, metadata


def build_faiss_index(descriptors: np.ndarray) -> Any:
    import faiss

    log.info("Building FAISS index for %d vectors (dim=%d)", descriptors.shape[0], descriptors.shape[1])
    index = faiss.IndexFlatIP(descriptors.shape[1])
    norms = np.linalg.norm(descriptors, axis=1, keepdims=True)
    norms[norms == 0] = 1
    normalized = descriptors / norms
    index.add(normalized.astype(np.float32))
    log.info("FAISS index built: %d vectors", index.ntotal)
    return index


def load_netryx_bundle(bundle_path: str, index_dir: str) -> dict[str, Any]:
    os.makedirs(index_dir, exist_ok=True)

    with zipfile.ZipFile(bundle_path, "r") as zf:
        manifest = json.loads(zf.read("manifest.json"))
        log.info("Extracting bundle: %s", manifest.get("name", "unknown"))

        file_mapping = {
            "descriptors.npy": "megaloc_descriptors.npy",
            "metadata.npz": "metadata.npz",
            "pca_model.pkl": "megaloc_pca.pkl",
            "index_info.txt": "index_info.txt",
            "manifest.json": "manifest.json",
        }

        for src_name, dst_name in file_mapping.items():
            if src_name in zf.namelist():
                data = zf.read(src_name)
                dst_path = os.path.join(index_dir, dst_name)
                with open(dst_path, "wb") as f:
                    f.write(data)
                log.debug("  Extracted %s -> %s", src_name, dst_name)

    log.info("Bundle loaded: %s", manifest.get("name", "unknown"))
    return manifest


def create_bundle(
    index_dir: str,
    output_path: str,
    name: str,
    description: str,
    center_lat: float,
    center_lon: float,
    radius_km: float,
    tags: list[str] | None = None,
    creator: str = "anonymous",
) -> tuple[str, dict[str, Any]]:
    import hashlib
    import json
    import shutil
    import tempfile
    import time

    descs_path = os.path.join(index_dir, "megaloc_descriptors.npy")
    meta_path = os.path.join(index_dir, "metadata.npz")
    pca_path = os.path.join(index_dir, "megaloc_pca.pkl")
    info_path = os.path.join(index_dir, "index_info.txt")

    if not os.path.exists(descs_path):
        descs_path = os.path.join(index_dir, "cosplace_descriptors.npy")
    if not os.path.exists(descs_path):
        raise FileNotFoundError(f"Descriptors not found in {index_dir}")
    if not os.path.exists(meta_path):
        raise FileNotFoundError(f"Metadata not found at {meta_path}")

    descs = np.load(descs_path, mmap_mode="r")
    meta = np.load(meta_path, allow_pickle=True)
    lats = meta["lats"]
    lons = meta["lons"]

    from utils.geo_utils import haversine_np

    distances = haversine_np(center_lat, center_lon, lats, lons)
    mask = distances <= (radius_km * 1.1)
    valid_idx = np.where(mask)[0]

    if len(valid_idx) == 0:
        raise ValueError(f"No entries within {radius_km}km of ({center_lat}, {center_lon})")

    log.info("Geographic filter: %d/%d entries within %.1fkm", len(valid_idx), len(descs), radius_km)

    num_entries = len(valid_idx)
    desc_dim = descs.shape[1]
    panoid_set = set(str(p) for p in meta["panoids"][valid_idx])

    manifest = {
        "format_version": "2.0",
        "name": name,
        "description": description,
        "creator": creator,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "center_lat": float(center_lat),
        "center_lon": float(center_lon),
        "radius_km": float(radius_km),
        "num_entries": int(num_entries),
        "num_panoids": len(panoid_set),
        "descriptor_dim": int(desc_dim),
        "raw_descriptor_dim": 8448,
        "descriptor_model": "MegaLoc",
        "pca_components": int(desc_dim),
        "tags": tags or [],
    }

    tmp_dir = tempfile.mkdtemp(prefix="netryx_bundle_", dir=os.path.dirname(os.path.abspath(output_path)) or None)
    try:
        tmp_descs = os.path.join(tmp_dir, "descriptors.npy")
        tmp_meta = os.path.join(tmp_dir, "metadata.npz")

        out_descs = np.lib.format.open_memmap(tmp_descs, mode="w+", dtype=np.float32, shape=(num_entries, desc_dim))
        chunk = 100_000
        for s in range(0, num_entries, chunk):
            idx_chunk = valid_idx[s : s + chunk]
            out_descs[s : s + len(idx_chunk)] = descs[idx_chunk]
        out_descs.flush()
        del out_descs, descs

        np.savez_compressed(
            tmp_meta,
            lats=meta["lats"][valid_idx],
            lons=meta["lons"][valid_idx],
            headings=meta["headings"][valid_idx],
            panoids=meta["panoids"][valid_idx],
            paths=meta["paths"][valid_idx],
        )

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))
            zf.write(tmp_descs, "descriptors.npy")
            zf.write(tmp_meta, "metadata.npz")
            if os.path.exists(pca_path):
                zf.write(pca_path, "pca_model.pkl")
            if os.path.exists(info_path):
                zf.write(info_path, "index_info.txt")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    _h = hashlib.sha256()
    with open(output_path, "rb") as _f:
        for _blk in iter(lambda: _f.read(1 << 24), b""):
            _h.update(_blk)
    manifest["sha256"] = _h.hexdigest()
    manifest["file_size_bytes"] = os.path.getsize(output_path)

    log.info("Bundle created: %s (%.0f MB)", output_path, os.path.getsize(output_path) / 1024 / 1024)
    return output_path, manifest
