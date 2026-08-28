import io
import logging
import os
import sys
from typing import Any

import uvicorn
from fastapi import FastAPI, File, Form, UploadFile
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("netryx.modal")

web_app = FastAPI(title="Netryx Nova Modal Worker")


@web_app.on_event("startup")
async def startup() -> None:
    _ensure_mast3r_imports()
    log.info("Modal worker ready")


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
        )
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
    uvicorn.run(web_app, host="0.0.0.0", port=8001)
