import os
from pathlib import Path

# ── Data Directory Resolution ──────────────────────────────────────────────
# Order: NETRYX_DATA_DIR env var -> config.json override -> ./netryx_data
_CONFIG_FILE = Path(__file__).parent / "config.json"

if os.environ.get("NETRYX_DATA_DIR"):
    DATA_DIR = os.environ["NETRYX_DATA_DIR"]
elif _CONFIG_FILE.exists():
    import json
    with open(_CONFIG_FILE) as _f:
        _cfg = json.load(_f)
    DATA_DIR = _cfg.get("data_dir", os.path.join(os.path.dirname(os.path.abspath(__file__)), "netryx_data"))
else:
    DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "netryx_data")

# ── Encoder Dimensions ─────────────────────────────────────────────────────
MEGALOC_RAW_DIM: int = 8448
MEGALOC_PCA_DIM: int = 1024
INDEX_TARGET_DIM: int = 1024

# ── Pipeline Thresholds ────────────────────────────────────────────────────
RETRIEVAL_TOP_K: int = 1000
MATCHING_TOP_K: int = 500
EARLY_EXIT_INLIER_THRESHOLD: int = 300

# ── Spatial Consensus ──────────────────────────────────────────────────────
CELL_SIZE_DEG: float = 0.00045 # ~50m grid
CONSENSUS_TOP_K: int = 10
NEIGHBORHOOD_RANGE: int = 1  # 3x3 neighborhood

# ── Pipeline Controller ────────────────────────────────────────────────────
MAX_CONCURRENT_GPU_JOBS: int = 1
MAX_CONCURRENT_CPU_JOBS: int = 2
JOB_CLEANUP_TIMEOUT_SECONDS: int = 300

# ── Performance Tuning ─────────────────────────────────────────────────────
MAX_PANOID_WORKERS: int = 32
MAX_HEADING_WORKERS: int = 4
MAX_DOWNLOAD_WORKERS: int = 120
MAX_MATCH_WORKERS: int = 16
MEGALOC_BATCH_SIZE: int = 64
CROP_QUEUE_SIZE: int = 1024
MAX_PCA_SAMPLES: int = 100_000

# ── Paths (relative to DATA_DIR) ───────────────────────────────────────────
MEGALOC_PARTS_DIR: str = os.path.join(DATA_DIR, "megaloc_parts")
EMB_CSV: str = os.path.join(DATA_DIR, "embeddings_index.csv")
COMPACT_INDEX_DIR: str = os.path.join(DATA_DIR, "index")
COMPACT_DESCS_PATH: str = os.path.join(COMPACT_INDEX_DIR, "megaloc_descriptors.npy")
COMPACT_META_PATH: str = os.path.join(COMPACT_INDEX_DIR, "metadata.npz")
COMPACT_INFO_PATH: str = os.path.join(COMPACT_INDEX_DIR, "index_info.txt")

# ── Server ─────────────────────────────────────────────────────────────────
HOST: str = "0.0.0.0"
PORT: int = 8000
