import sys, os, tempfile, shutil
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from utils.netryx_loader import load_netryx_bundle
from core.retrieval import load_or_build_index, search_index
import numpy as np

tmp = tempfile.mkdtemp()
try:
    bundle_path = os.path.join(PROJECT_ROOT, "tests/fixtures/test_fixture_50.netryx")
    m = load_netryx_bundle(bundle_path, tmp)
    idx, meta = load_or_build_index(tmp, use_faiss=True, force_reload=True)

    query = np.random.randn(1024).astype(np.float32)
    results = search_index(query, (55.7558, 37.6173), 10.0, top_k=5, index_dir=tmp)
    print(f"Search returned {len(results)} results")
    for r in results:
        pid = r.get("panoid", "?")
        print(f"  {pid}: score={r['score']:.4f}, lat={r['lat']:.4f}, lon={r['lon']:.4f}")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
