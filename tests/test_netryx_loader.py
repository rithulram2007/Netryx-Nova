import importlib
import os
import sys
import tempfile

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.netryx_loader import build_faiss_index, load_compact_index, load_netryx_bundle

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "test_fixture_50.netryx")

_HAS_FAISS = importlib.util.find_spec("faiss") is not None


def test_load_bundle_extracts_files():
    tmp = tempfile.mkdtemp()
    manifest = load_netryx_bundle(FIXTURE, tmp)
    assert os.path.exists(os.path.join(tmp, "megaloc_descriptors.npy"))
    assert os.path.exists(os.path.join(tmp, "metadata.npz"))
    assert os.path.exists(os.path.join(tmp, "manifest.json"))
    assert manifest["num_entries"] == 50


def test_load_compact_index_returns_data():
    tmp = tempfile.mkdtemp()
    load_netryx_bundle(FIXTURE, tmp)
    descs, meta = load_compact_index(tmp)
    assert descs is not None
    assert meta is not None
    assert descs.shape == (50, 1024)
    assert len(meta["lats"]) == 50
    assert len(meta["lons"]) == 50
    assert len(meta["panoids"]) == 50
    assert len(meta["headings"]) == 50


def test_load_compact_index_missing():
    descs, meta = load_compact_index("/nonexistent")
    assert descs is None
    assert meta is None


@pytest.mark.skipif(not _HAS_FAISS, reason="faiss not installed")
def test_build_faiss_index():
    descs = np.random.randn(50, 1024).astype(np.float32)
    index = build_faiss_index(descs)
    assert index.ntotal == 50


@pytest.mark.skipif(not _HAS_FAISS, reason="faiss not installed")
def test_build_faiss_normalization():
    rng = np.random.default_rng(42)
    descs = rng.normal(size=(10, 1024)).astype(np.float32)
    index = build_faiss_index(descs)
    norms = np.linalg.norm(descs, axis=1)
    query = (descs[0] / norms[0]).astype(np.float32).reshape(1, -1)
    scores, _ = index.search(query, 5)
    assert scores[0][0] > 0.99
