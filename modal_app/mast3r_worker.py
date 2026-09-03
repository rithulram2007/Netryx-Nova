import io
import logging
import os
import sys
import tempfile
from typing import Any

import numpy as np
import uvicorn
from fastapi import FastAPI, File, Form, UploadFile
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("netryx.modal")

web_app = FastAPI(title="Netryx Nova Modal Worker")


def _ensure_app_imports() -> None:
    os.environ["INSIDE_MODAL"] = "1"
    candidates = [
        os.path.abspath("."),
        os.path.abspath(".."),
        os.path.abspath("/root/app"),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
    ]
    for c in candidates:
        if os.path.exists(os.path.join(c, "core", "retrieval.py")):
            if c not in sys.path:
                sys.path.insert(0, c)
            return


@web_app.on_event("startup")
async def startup() -> None:
    _ensure_mast3r_imports()
    _ensure_app_imports()
    log.info("Modal worker ready")


@web_app.post("/search")
async def search(
    query: UploadFile = File(None),
    lat: float = Form(0.0),
    lon: float = Form(0.0),
    radius: float = Form(0.5),
    top_k: int = Form(1000),
    repo_name: str = Form(None),
) -> dict[str, Any]:
    _ensure_app_imports()
    try:
        from config import COMPACT_INDEX_DIR
        from core.retrieval import load_or_build_index, search_index

        if repo_name:
            try:
                from netryx_hub import NetryxHub
                hub = NetryxHub()
                hub.download(repo_name, COMPACT_INDEX_DIR)
                load_or_build_index(use_faiss=True, force_reload=True)
            except Exception as ex:
                log.warning("Failed to download requested repo %s: %s", repo_name, ex)

        try:
            load_or_build_index(use_faiss=True)
        except Exception:
            try:
                from netryx_hub import NetryxHub
                hub = NetryxHub()
                hub.download("netryx-hub/moscow-1km-1km", COMPACT_INDEX_DIR)
                load_or_build_index(use_faiss=True, force_reload=True)
            except Exception as ex:
                log.error("Failed to load index on Modal: %s", ex)
                return {"candidates": [], "status": "error", "error": str(ex)}

        query_np = None
        if query:
            query_bytes = await query.read()
            if len(query_bytes) == 1024 * 4:
                query_np = np.frombuffer(query_bytes, dtype=np.float32)
            elif len(query_bytes) > 0:
                try:
                    query_img = Image.open(io.BytesIO(query_bytes)).convert("RGB")
                    arr = np.array(query_img.resize((32, 32)), dtype=np.float32).flatten()
                    query_np = arr[:1024]
                    if len(query_np) < 1024:
                        query_np = np.pad(query_np, (0, 1024 - len(query_np)))
                except Exception:
                    query_np = np.zeros((1024,), dtype=np.float32)

        if query_np is None or len(query_np) != 1024:
            query_np = np.zeros((1024,), dtype=np.float32)

        candidates = search_index(
            query_desc=query_np,
            center=(lat, lon),
            radius_km=radius,
            top_k=top_k,
        )
        return {"candidates": candidates, "status": "ok"}
    except Exception as e:
        log.exception("Modal search failed")
        return {"candidates": [], "status": "error", "error": str(e)}


@web_app.post("/index/hub/download")
async def modal_hub_download(repo_name: str = Form(...)) -> dict[str, Any]:
    _ensure_app_imports()
    try:
        from config import COMPACT_INDEX_DIR
        from core.retrieval import load_or_build_index, reset_index
        from netryx_hub import NetryxHub

        os.makedirs(COMPACT_INDEX_DIR, exist_ok=True)
        hub = NetryxHub()
        manifest = hub.download(repo_name, COMPACT_INDEX_DIR)
        reset_index()
        load_or_build_index(use_faiss=True, force_reload=True)
        return {"status": "ok", "message": f"Downloaded {repo_name}", "manifest": manifest}
    except Exception as e:
        log.exception("Modal index hub download failed")
        return {"status": "error", "error": str(e)}


@web_app.post("/index/load")
async def modal_index_load(file: UploadFile = File(...)) -> dict[str, Any]:
    _ensure_app_imports()
    try:
        from config import COMPACT_INDEX_DIR
        from core.retrieval import load_or_build_index, reset_index
        from utils.netryx_loader import load_netryx_bundle

        os.makedirs(COMPACT_INDEX_DIR, exist_ok=True)
        tmp_path = os.path.join(tempfile.gettempdir(), file.filename or "index.netryx")
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)

        manifest = load_netryx_bundle(tmp_path, COMPACT_INDEX_DIR)
        reset_index()
        load_or_build_index(use_faiss=True, force_reload=True)
        return {"status": "ok", "message": f"Index loaded: {manifest.get('name', 'unknown')}"}
    except Exception as e:
        log.exception("Modal index load failed")
        return {"status": "error", "error": str(e)}
    finally:
        if "tmp_path" in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@web_app.get("/index/info")
async def modal_index_info() -> dict[str, Any]:
    _ensure_app_imports()
    try:
        from core.exceptions import IndexNotFoundError
        from core.retrieval import load_or_build_index

        _, metadata = load_or_build_index(use_faiss=True)
        lats = metadata["lats"]
        return {
            "loaded": True,
            "entries": len(lats),
            "panoids": int(metadata.get("panoids", []).shape[0] if hasattr(metadata.get("panoids"), "shape") else 0),
            "lat_range": [float(lats.min()), float(lats.max())],
            "lon_range": [float(metadata["lons"].min()), float(metadata["lons"].max())],
            "heading_step": 90,
        }
    except Exception:
        return {"loaded": False, "entries": 0}


@web_app.get("/index/coverage")
async def modal_index_coverage() -> dict[str, Any]:
    _ensure_app_imports()
    try:
        from core.exceptions import IndexNotFoundError
        from core.retrieval import load_or_build_index

        _, metadata = load_or_build_index(use_faiss=True)
        lats = metadata["lats"]
        lons = metadata["lons"]

        step = max(1, len(lats) // 1000)
        features = []
        for i in range(0, len(lats), step):
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(lons[i]), float(lats[i])]},
                "properties": {"panoid": str(metadata["panoids"][i])},
            })

        return {
            "type": "FeatureCollection",
            "features": features,
            "properties": {
                "total_entries": len(lats),
                "sampled": len(features),
            },
        }
    except Exception:
        return {"type": "FeatureCollection", "features": []}


@web_app.post("/match")
async def match(
    query: UploadFile = File(...),
    panoid: str = Form(...),
    heading: int = Form(...),
    lat: float = Form(0.0),
    lon: float = Form(0.0),
    crop_fov: int = Form(90),
    crop_size: int = Form(256),
) -> dict[str, Any]:
    import mast3r_utils as mu
    from utils.geo_utils import equirectangular_to_rectilinear
    from utils.tile_downloader import download_tiles, stitch_tiles, tiles_info

    query_bytes = await query.read()
    query_img = Image.open(io.BytesIO(query_bytes)).convert("RGB")
    query_img_resize = query_img.resize((crop_size, crop_size), Image.BILINEAR)

    model = mu.get_mast3r_model()
    if model is None:
        return {"inliers": 0, "error": "MASt3R model not available", "panoid": panoid}

    try:
        tiles = tiles_info(panoid)
        td = download_tiles(tiles, max_workers=16)
        if not td:
            return {"inliers": 0, "error": "tile download failed", "panoid": panoid}

        pano_img = stitch_tiles(td)
        maxw = 2048
        if pano_img.size[0] > maxw:
            ratio = maxw / pano_img.size[0]
            pano_img = pano_img.resize((maxw, int(pano_img.size[1] * ratio)), Image.BILINEAR)

        crop_pil = equirectangular_to_rectilinear(
            pano_img, fov_deg=float(crop_fov),
            out_hw=(crop_size, crop_size), yaw_deg=heading,
        )
        m0, m1, _ = mu.get_mast3r_matches(query_img_resize, crop_pil, model)
        score = len(m0)

        return {
            "inliers": score,
            "panoid": panoid,
            "heading": heading,
            "lat": lat,
            "lon": lon,
        }

    except Exception as e:
        log.exception("Match failed for %s", panoid)
        return {"inliers": 0, "error": str(e), "panoid": panoid}


@web_app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ── Modal entrypoint ──────────────────────────────────────────────────────

try:
    import modal

    app = modal.App("netryx-nova-worker")
    _MODAL_IMAGE = (
        modal.Image.debian_slim(python_version="3.11")
        .apt_install("git")
        .run_commands(
            "git clone --recursive https://github.com/naver/mast3r.git /mast3r",
        )
        .uv_pip_install(
            "torch>=2.0",
            "torchvision",
            "numpy",
            "Pillow",
            "aiohttp",
            "fastapi",
            "uvicorn[standard]",
            "python-multipart",
            "requests",
            "safetensors",
            "einops",
            "timm",
            "scikit-learn",
            "faiss-cpu",
            "huggingface_hub",
        )
        .add_local_dir(".", remote_path="/root/app", copy=True)
    )

    @app.function(
        image=_MODAL_IMAGE,
        gpu="T4",
        timeout=600,
        scaledown_window=120,
        secrets=[modal.Secret.from_name("netryx-hf-token")],
    )
    @modal.asgi_app()
    def fastapi_app() -> FastAPI:
        _ensure_mast3r_imports()
        _ensure_app_imports()
        return web_app

except ImportError:
    log.info("modal not installed — worker can only run locally")
    app = None


def _ensure_mast3r_imports() -> None:
    mast3r_candidates = [
        os.path.abspath("/mast3r"),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mast3r")),
        os.path.expanduser("~/mast3r"),
    ]
    for candidate in mast3r_candidates:
        mast3r_pkg = os.path.join(candidate, "mast3r", "model.py")
        if os.path.exists(mast3r_pkg):
            if candidate not in sys.path:
                sys.path.insert(0, candidate)
            dust3r_dir = os.path.join(candidate, "dust3r")
            if os.path.exists(dust3r_dir) and dust3r_dir not in sys.path:
                sys.path.insert(0, dust3r_dir)
            log.info("MASt3R found at %s", candidate)
            return
    log.warning("MASt3R not found — worker will return errors")


# ── Local dev entrypoint ──────────────────────────────────────────────────

if __name__ == "__main__":
    _ensure_mast3r_imports()
    _ensure_app_imports()
    uvicorn.run(web_app, host="0.0.0.0", port=8001)
