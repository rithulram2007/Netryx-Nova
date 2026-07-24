import logging
import math
from collections import defaultdict
from typing import Any

from config import CELL_SIZE_DEG, CONSENSUS_TOP_K, NEIGHBORHOOD_RANGE

log = logging.getLogger("netryx.consensus")


def spatial_consensus(
    scored_matches: list[dict[str, Any]],
    top_k: int = CONSENSUS_TOP_K,
    cell_size: float = CELL_SIZE_DEG,
    neighborhood_range: int = NEIGHBORHOOD_RANGE,
) -> list[dict[str, Any]]:
    if not scored_matches:
        return []

    cells: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for m in scored_matches:
        cell = (round(m["lat"] / cell_size), round(m["lon"] / cell_size))
        cells[cell].append(m)

    scored_clusters: list[dict[str, Any]] = []
    for cell_matches in cells.values():
        neighborhood: list[dict[str, Any]] = []
        cell_key = (
            round(cell_matches[0]["lat"] / cell_size),
            round(cell_matches[0]["lon"] / cell_size),
        )
        for dlat in range(-neighborhood_range, neighborhood_range + 1):
            for dlon in range(-neighborhood_range, neighborhood_range + 1):
                neighbor = (cell_key[0] + dlat, cell_key[1] + dlon)
                neighborhood.extend(cells.get(neighbor, []))

        cell_score = sum(math.sqrt(m["inliers"]) for m in neighborhood)
        cluster_best = max(neighborhood, key=lambda m: m["inliers"])
        scored_clusters.append({"score": cell_score, "match": cluster_best})

    scored_clusters.sort(key=lambda x: x["score"], reverse=True)

    top_results: list[dict[str, Any]] = []
    seen_pids: set[str] = set()
    for sc in scored_clusters:
        r = sc["match"]
        if r.get("panoid") not in seen_pids:
            top_results.append(r)
            seen_pids.add(r["panoid"])
        if len(top_results) >= top_k:
            break

    log.info("Consensus: %d clusters, %d unique top results", len(scored_clusters), len(top_results))
    return top_results
