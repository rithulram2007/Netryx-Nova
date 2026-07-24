import json
import logging
import os
import tempfile

from fastapi import APIRouter, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from PIL import Image

from config import COMPACT_INDEX_DIR
from core.exceptions import IndexNotFoundError
from core.pipeline import PipelineController
from core.retrieval import load_or_build_index, reset_index
from utils.netryx_loader import load_netryx_bundle

log = logging.getLogger("netryx.web")

router = APIRouter(prefix="/api/v1")
pipeline = PipelineController()


@router.get("/index/info")
async def index_info() -> JSONResponse:
    try:
        _, metadata = load_or_build_index()
        lats = metadata["lats"]
        entries = len(lats)
        info = {
            "loaded": True,
            "entries": entries,
            "panoids": int(metadata.get("panoids", []).shape[0] if hasattr(metadata.get("panoids"), "shape") else 0),
            "lat_range": [float(lats.min()), float(lats.max())],
            "lon_range": [float(metadata["lons"].min()), float(metadata["lons"].max())],
            "heading_step": 90,
        }
        return JSONResponse(content=info)
    except IndexNotFoundError:
        return JSONResponse(content={"loaded": False, "entries": 0}, status_code=200)


@router.post("/index/load")
async def index_load(file: UploadFile = File(...)) -> JSONResponse:
    if not file.filename or not file.filename.endswith(".netryx"):
        return JSONResponse(content={"error": "File must be a .netryx bundle"}, status_code=400)

    os.makedirs(COMPACT_INDEX_DIR, exist_ok=True)

    tmp_path = os.path.join(tempfile.gettempdir(), file.filename)
    try:
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)

        manifest = load_netryx_bundle(tmp_path, COMPACT_INDEX_DIR)
        reset_index()
        load_or_build_index(force_reload=True)

        info = {
            "status": "ok",
            "message": f"Index loaded: {manifest.get('name', 'unknown')}",
            "entries": os.path.getsize(os.path.join(COMPACT_INDEX_DIR, "megaloc_descriptors.npy")) // (4 * 1024),
        }
        return JSONResponse(content=info)
    except Exception as e:
        log.exception("Failed to load index")
        return JSONResponse(content={"error": str(e)}, status_code=500)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.get("/index/hub/list")
async def hub_list() -> JSONResponse:
    try:
        from netryx_hub import NetryxHub
        hub = NetryxHub()
        indexes = hub.list_indexes()
        return JSONResponse(content={"indexes": indexes})
    except ImportError:
        return JSONResponse(content={"error": "huggingface_hub not installed", "indexes": []}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": str(e), "indexes": []}, status_code=200)


@router.post("/index/hub/download")
async def hub_download(repo_name: str = Form(...)) -> JSONResponse:
    try:
        from netryx_hub import NetryxHub
        hub = NetryxHub()
        os.makedirs(COMPACT_INDEX_DIR, exist_ok=True)
        manifest = hub.download(repo_name, COMPACT_INDEX_DIR)
        reset_index()
        load_or_build_index(force_reload=True)
        return JSONResponse(content={"status": "ok", "message": f"Downloaded {repo_name}", "manifest": manifest})
    except ImportError:
        return JSONResponse(content={"error": "huggingface_hub not installed"}, status_code=400)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.post("/search/run")
async def search_run(
    file: UploadFile = File(...),
    lat: float = Form(...),
    lon: float = Form(...),
    radius: float = Form(0.5),
    engine: str = Form("auto"),
) -> JSONResponse:
    if not file.filename:
        return JSONResponse(content={"error": "No file provided"}, status_code=400)

    try:
        content = await file.read()
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.write(content)
        tmp.close()

        img = Image.open(tmp.name).convert("RGB")
        job_id = pipeline.create_job(
            query_img=img,
            lat=lat,
            lon=lon,
            radius_km=radius,
            engine_prefer=engine,
        )
        return JSONResponse(content={"job_id": job_id, "status": "queued"}, status_code=202)
    except Exception as e:
        log.exception("Search run failed")
        return JSONResponse(content={"error": str(e)}, status_code=500)
    finally:
        if "tmp" in dir() and os.path.exists(tmp.name):
            os.unlink(tmp.name)


@router.get("/search/status/{job_id}")
async def search_status(job_id: str) -> JSONResponse:
    status = pipeline.get_job_status(job_id)
    if status is None:
        return JSONResponse(content={"error": "Job not found"}, status_code=404)
    return JSONResponse(content=status)


@router.websocket("/ws/search")
async def ws_search(websocket: WebSocket) -> None:
    job_id = websocket.query_params.get("job_id")
    if not job_id:
        await websocket.close(code=4000, reason="Missing job_id")
        return

    await websocket.accept()
    log.info("WS client connected for job %s", job_id)

    try:
        last_current = -1
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "cancel":
                pipeline.cancel_job(job_id)
                await websocket.send_json({"type": "cancelled", "message": "Job cancelled"})
                break
    except WebSocketDisconnect:
        log.debug("WS client disconnected for job %s", job_id)
        return

    try:
        while True:
            status = pipeline.get_job_status(job_id)
            if status is None:
                await websocket.send_json({"type": "error", "message": "Job not found"})
                break

            for msg in status.get("progress_messages", []):
                await websocket.send_json(msg)
                if "current" in msg and msg["current"] != last_current:
                    last_current = msg["current"]

            if status["status"] in ("complete", "failed", "cancelled"):
                if "result" in status:
                    await websocket.send_json({"type": "complete", "result": status["result"]})
                elif "error" in status:
                    await websocket.send_json({"type": "error", "message": status["error"]})
                break

            await websocket.send_json({"type": "ping"})
            import asyncio
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass


@router.get("/index/coverage")
async def index_coverage() -> JSONResponse:
    try:
        _, metadata = load_or_build_index()
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

        geojson = {
            "type": "FeatureCollection",
            "features": features,
            "properties": {
                "total_entries": len(lats),
                "sampled": len(features),
            },
        }
        return JSONResponse(content=geojson)
    except IndexNotFoundError:
        return JSONResponse(content={"type": "FeatureCollection", "features": []})
