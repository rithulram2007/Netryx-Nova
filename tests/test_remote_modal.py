import pytest
from fastapi.testclient import TestClient

from app import app
from core.retrieval import search_index, use_remote_modal
from engines.cloud_modal import CloudModalEngine

client = TestClient(app)


def test_use_remote_modal_env(monkeypatch):
    monkeypatch.setenv("RENDER", "1")
    assert use_remote_modal() is True

    monkeypatch.delenv("RENDER")
    monkeypatch.setenv("USE_REMOTE_MODAL", "1")
    assert use_remote_modal() is True

    monkeypatch.delenv("USE_REMOTE_MODAL")
    assert use_remote_modal() is False


def test_cloud_modal_engine_methods(monkeypatch):
    engine = CloudModalEngine(endpoint_url="http://localhost:8001")

    def mock_post(url, *args, **kwargs):
        class MockResp:
            status_code = 200
            def json(self):
                if "/search" in url:
                    return {"status": "ok", "candidates": [{"panoid": "test_pano", "heading": 90, "lat": 55.75, "lon": 37.61, "score": 0.95}]}
                if "/index/hub/download" in url:
                    return {"status": "ok", "message": "Downloaded repo"}
                if "/index/load" in url:
                    return {"status": "ok", "message": "Loaded bundle"}
                return {}
        return MockResp()

    def mock_get(url, *args, **kwargs):
        class MockResp:
            status_code = 200
            def json(self):
                if "/index/info" in url:
                    return {"loaded": True, "entries": 34496}
                if "/index/coverage" in url:
                    return {"type": "FeatureCollection", "features": []}
                return {}
        return MockResp()

    monkeypatch.setattr("requests.post", mock_post)
    monkeypatch.setattr("requests.get", mock_get)

    cands = engine.search_index(None, (55.75, 37.61), 1.0, 10)
    assert len(cands) == 1
    assert cands[0]["panoid"] == "test_pano"

    info = engine.get_index_info()
    assert info["loaded"] is True
    assert info["entries"] == 34496

    dl = engine.download_hub_index("netryx-hub/moscow-1km-1km")
    assert dl["status"] == "ok"

    ul = engine.upload_index(b"dummy", "index.netryx")
    assert ul["status"] == "ok"

    cov = engine.get_index_coverage()
    assert cov["type"] == "FeatureCollection"


def test_web_app_remote_routing(monkeypatch):
    monkeypatch.setenv("USE_REMOTE_MODAL", "1")

    def mock_post(url, *args, **kwargs):
        class MockResp:
            status_code = 200
            def json(self):
                return {"status": "ok", "message": "Remote action success"}
        return MockResp()

    def mock_get(url, *args, **kwargs):
        class MockResp:
            status_code = 200
            def json(self):
                if "/index/info" in url:
                    return {"loaded": True, "entries": 100}
                if "/index/coverage" in url:
                    return {"type": "FeatureCollection", "features": []}
                return {}
        return MockResp()

    monkeypatch.setattr("requests.post", mock_post)
    monkeypatch.setattr("requests.get", mock_get)

    resp_info = client.get("/api/v1/index/info")
    assert resp_info.status_code == 200
    assert resp_info.json()["loaded"] is True

    resp_cov = client.get("/api/v1/index/coverage")
    assert resp_cov.status_code == 200
    assert resp_cov.json()["type"] == "FeatureCollection"

    resp_dl = client.post("/api/v1/index/hub/download", data={"repo_name": "netryx-hub/moscow-1km-1km"})
    assert resp_dl.status_code == 200
    assert resp_dl.json()["status"] == "ok"
