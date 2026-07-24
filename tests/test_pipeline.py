import os
import sys
import tempfile

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.retrieval import load_or_build_index, reset_index, search_index
from utils.netryx_loader import load_netryx_bundle

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "test_fixture_50.netryx")


@pytest.fixture(autouse=True)
def reset():
    reset_index()
    yield


def test_pipeline_integration():
    tmp = tempfile.mkdtemp()
    try:
        load_netryx_bundle(FIXTURE, tmp)
        load_or_build_index(tmp, use_faiss=True, force_reload=True)

        query = np.random.randn(1024).astype(np.float32)
        results = search_index(query, (55.7558, 37.6173), 10.0, top_k=10, index_dir=tmp)

        assert len(results) > 0
        for r in results:
            assert "panoid" in r
            assert "lat" in r
            assert "lon" in r
            assert "score" in r
            assert "heading" in r
            assert isinstance(r["score"], float)
            assert r["score"] >= -1.0
            assert r["score"] <= 1.0
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
        reset_index()
