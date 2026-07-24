import asyncio
import io
import itertools
import logging
import re
from typing import Any

import aiohttp
import numpy as np
from PIL import Image

log = logging.getLogger("netryx.tile")

IMGX = 4
IMGY = 2
TILE_SIZE = 512

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Referer": "https://www.google.com/maps/",
}


def _panoids_url(lat: float, lon: float) -> str:
    url = (
        "https://maps.googleapis.com/maps/api/js/GeoPhotoService.SingleImageSearch"
        "?pb=!1m5!1sapiv3!5sUS!11m2!1m1!1b0!2m4!1m2!3d{0:}!4d{1:}!2d50"
        "!3m10!2m2!1en!2sGB!9m1!1e2!11m4!1m3!1e2!2b1!3e2"
        "!4m10!1e1!1e2!1e3!1e4!1e8!1e6!5m1!1e2!6m1!1e2&callback=_xdc_._v2mub5"
    )
    return url.format(lat, lon)


def panoids_from_response(text: str) -> list[dict[str, Any]]:
    matches = re.findall(r'"([A-Za-z0-9_-]{22})"', text)
    out: list[dict[str, Any]] = []
    for panoid in matches:
        latlon = re.findall(r'"' + panoid + r'".+?\[null,null,(-?\d+\.\d+),(-?\d+\.\d+)', text)
        if latlon:
            lat, lon = map(float, latlon[0])
        else:
            lat, lon = None, None
        out.append({"panoid": panoid, "lat": lat, "lon": lon})

    seen: set[str] = set()
    filtered: list[dict[str, Any]] = []
    for p in out:
        if p["panoid"] not in seen:
            seen.add(p["panoid"])
            filtered.append(p)
    return filtered


def tiles_info(panoid: str) -> list[tuple[int, int, str, str]]:
    image_url = (
        "https://streetviewpixels-pa.googleapis.com/v1/tile"
        "?cb_client=maps_sv.tactile&panoid={0:}&x={1:}&y={2:}&zoom=2&nbt=1&fover=2"
    )
    coord = list(itertools.product(range(IMGX), range(IMGY)))
    return [(x, y, f"{panoid}_{x}x{y}.jpg", image_url.format(panoid, x, y)) for x, y in coord]


async def download_tile_aiohttp(
    session: aiohttp.ClientSession, x: int, y: int, fname: str, url: str
) -> tuple[int, int, bytes | None]:
    for attempt in range(2):
        try:
            async with session.get(url.replace("http://", "https://"), timeout=10) as response:
                if response.status == 200:
                    data = await response.read()
                    return x, y, data
        except Exception:
            await asyncio.sleep(2)
    return x, y, None


def download_tiles(
    tiles: list[tuple[int, int, str, str]],
    status_callback: Any = None,
    max_workers: int = 64,
) -> dict[tuple[int, int], bytes]:
    total = len(tiles)
    results: dict[tuple[int, int], bytes] = {}

    async def main() -> None:
        connector = aiohttp.TCPConnector(limit=max_workers)
        async with aiohttp.ClientSession(connector=connector, headers=_HEADERS) as session:
            tasks = []
            for x, y, fname, url in tiles:
                tasks.append(download_tile_aiohttp(session, x, y, fname, url))
            for idx, coro in enumerate(asyncio.as_completed(tasks), 1):
                x, y, data = await coro
                if data:
                    results[(x, y)] = data
                if status_callback:
                    status_callback(idx, total)

    asyncio.run(main())
    return results


def stitch_tiles(tiles_data: dict[tuple[int, int], bytes]) -> Image.Image:
    pano_np = np.zeros((IMGY * TILE_SIZE, IMGX * TILE_SIZE, 3), dtype=np.uint8)
    for (x, y), data in tiles_data.items():
        try:
            tile = Image.open(io.BytesIO(data))
            tile_np = np.array(tile)
            th, tw, _ = tile_np.shape
            pano_np[y * TILE_SIZE : y * TILE_SIZE + th, x * TILE_SIZE : x * TILE_SIZE + tw] = tile_np
            tile.close()
        except Exception:
            continue
    return Image.fromarray(pano_np)
