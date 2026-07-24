import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.netryx_loader import build_faiss_index

SIZES = [1_000, 10_000, 50_000, 100_000]
DESC_DIM = 1024
WARMUP = 10
REPEATS = 50


def benchmark() -> None:
    print(f"{'Size':>10} | {'Build(ms)':>10} | {'Search(ms)':>10} | {'QPS':>10} | {'Entries/s':>12}")
    print("-" * 60)

    for size in SIZES:
        rng = np.random.default_rng(123)

        t0 = time.perf_counter()
        index = build_faiss_index(rng.normal(size=(size, DESC_DIM)).astype(np.float32))
        t1 = time.perf_counter()
        build_ms = (t1 - t0) * 1000

        query = rng.normal(size=DESC_DIM).astype(np.float32)
        query = query / (np.linalg.norm(query) + 1e-8)

        for _ in range(WARMUP):
            index.search(query.reshape(1, -1), 1000)

        times = []
        for _ in range(REPEATS):
            t0 = time.perf_counter()
            index.search(query.reshape(1, -1), 1000)
            times.append(time.perf_counter() - t0)

        avg_ms = np.mean(times) * 1000
        qps = 1.0 / np.mean(times)
        entries_per_s = size / np.mean(times) / 1_000_000

        print(f"{size:>10} | {build_ms:>10.2f} | {avg_ms:>10.2f} | {qps:>10.0f} | {entries_per_s:>10.2f}M")


if __name__ == "__main__":
    benchmark()
