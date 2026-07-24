import os
import sys
import tempfile

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.exceptions import IndexNotFoundError
from core.retrieval import load_or_build_index, reset_index, search_index
from utils.netryx_loader import load_netryx_bundle

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "test_fixture_50.netryx")


@pytest.fixture(autouse=True)
def reset_global():
    reset_index()
    yield
    reset_index()


@pytest.fixture
def index_dir():
    tmp = tempfile.mkdtemp()
    load_netryx_bundle(FIXTURE, tmp)
    yield tmp


def test_load_index_faiss(index_dir):
    idx, meta = load_or_build_index(index_dir, use_faiss=True, force_reload=True)
    assert meta["lats"] is not None
    assert len(meta["lats"]) == 50


def test_load_index_numpy(index_dir):
    idx, meta = load_or_build_index(index_dir, use_faiss=False, force_reload=True)
    assert meta["lats"] is not None
    assert len(meta["lats"]) == 50


def test_load_index_cached(index_dir):
    idx1, _ = load_or_build_index(index_dir, force_reload=True)
    idx2, _ = load_or_build_index(index_dir)
    assert idx2 is idx1


def test_load_index_not_found():
    with pytest.raises(IndexNotFoundError):
        load_or_build_index("/nonexistent/path", force_reload=True)


def test_search_returns_results(index_dir):
    load_or_build_index(index_dir, force_reload=True)
    query = np.random.randn(1024).astype(np.float32)
    results = search_index(query, (55.7558, 37.6173), 10.0, top_k=5, index_dir=index_dir)
    assert len(results) <= 5
    assert len(results) > 0


def test_search_deduplicates_panoids(index_dir):
    load_or_build_index(index_dir, force_reload=True)
    query = np.random.randn(1024).astype(np.float32)
    results = search_index(query, (55.7558, 37.6173), 10.0, top_k=50, index_dir=index_dir)
    panoids = [r["panoid"] for r in results]
    assert len(panoids) == len(set(panoids))


def test_search_radius_filter(index_dir):
    load_or_build_index(index_dir, force_reload=True)
    query = np.random.randn(1024).astype(np.float32)
    far_results = search_index(query, (0.0, 0.0), 1.0, top_k=5, index_dir=index_dir)
    near_results = search_index(query, (55.7558, 37.6173), 10.0, top_k=5, index_dir=index_dir)
    assert len(far_results) < len(near_results)
