import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.tile_downloader import tiles_info


def test_tiles_info_returns_list():
    result = tiles_info("test_panoid_12345")
    assert isinstance(result, list)
    assert len(result) > 0


def test_tiles_info_contains_expected_fields():
    result = tiles_info("test_panoid_12345")
    tile = result[0]
    x, y, filename, url = tile
    assert isinstance(x, int)
    assert isinstance(y, int)
    assert isinstance(filename, str)
    assert filename.endswith(".jpg")
    assert url.startswith("https://")


def test_tiles_info_zoom_level():
    tiles = tiles_info("any_panoid")
    x, y, filename, url = tiles[0]
    assert "zoom=2" in url


def test_tiles_info_grid_size():
    tiles = tiles_info("pano")
    assert len(tiles) == 8
