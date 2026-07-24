import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.consensus import spatial_consensus


def make_match(inliers, panoid, lat, lon, heading=0):
    return {"inliers": inliers, "panoid": panoid, "heading": heading, "lat": lat, "lon": lon}


def test_empty():
    assert spatial_consensus([]) == []


def test_single_match():
    m = make_match(100, "p1", 55.75, 37.62)
    result = spatial_consensus([m])
    assert len(result) == 1
    assert result[0]["panoid"] == "p1"


def test_multiple_matches_same_cell():
    matches = [
        make_match(100, "p1", 55.755, 37.618),
        make_match(50, "p2", 55.756, 37.619),
    ]
    result = spatial_consensus(matches, top_k=2)
    assert len(result) == 2
    assert result[0]["inliers"] >= result[1]["inliers"]


def test_panoid_dedup():
    matches = [
        make_match(100, "p1", 55.755, 37.618),
        make_match(200, "p1", 55.756, 37.619),
    ]
    result = spatial_consensus(matches, top_k=5)
    assert len(result) == 1


def test_top_k_respected():
    matches = [make_match(i * 10, f"p{i}", 55.75 + i * 0.001, 37.62 + i * 0.001) for i in range(20)]
    result = spatial_consensus(matches, top_k=3)
    assert len(result) == 3


def test_cluster_scoring():
    dense = [make_match(100, "p1", 55.755, 37.618)]
    sparse = [make_match(100, "p2", 55.8, 37.7)]
    result = spatial_consensus(dense + sparse, top_k=2)
    assert len(result) == 2
