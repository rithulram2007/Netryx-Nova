import json
import os
import tempfile
import zipfile

import numpy as np

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
NUM_ENTRIES = 50
DESC_DIM = 1024
CENTER_LAT = 55.7558
CENTER_LON = 37.6173


def generate_fixtures(output_dir: str | None = None) -> str:
    if output_dir is None:
        output_dir = FIXTURE_DIR
    os.makedirs(output_dir, exist_ok=True)

    rng = np.random.default_rng(42)

    descs = rng.normal(size=(NUM_ENTRIES, DESC_DIM)).astype(np.float32)
    norms = np.linalg.norm(descs, axis=1, keepdims=True)
    norms[norms == 0] = 1
    descs = descs / norms

    lats = CENTER_LAT + rng.uniform(-0.05, 0.05, size=NUM_ENTRIES)
    lons = CENTER_LON + rng.uniform(-0.05, 0.05, size=NUM_ENTRIES)
    headings = rng.integers(0, 360, size=NUM_ENTRIES).astype(np.int16)
    alphabet = list("abcdefghijklmnopqrstuvwxyz0123456789")
    panoids = [
        f"pano_{i:04d}_{''.join(rng.choice(alphabet, size=6))}"
        for i in range(NUM_ENTRIES)
    ]
    paths = [f"parts/{p}_{h}.npz" for p, h in zip(panoids, headings)]

    manifest = {
        "format_version": "2.0",
        "name": "Test Fixture 50",
        "description": "Synthetic test fixture with 50 entries",
        "creator": "test",
        "created_at": "2026-07-24T00:00:00Z",
        "center_lat": CENTER_LAT,
        "center_lon": CENTER_LON,
        "radius_km": 5.0,
        "num_entries": NUM_ENTRIES,
        "num_panoids": NUM_ENTRIES,
        "descriptor_dim": DESC_DIM,
        "raw_descriptor_dim": 8448,
        "descriptor_model": "MegaLoc",
        "pca_components": DESC_DIM,
        "tags": ["test", "fixture"],
    }

    bundle_path = os.path.join(output_dir, "test_fixture_50.netryx")

    with tempfile.TemporaryDirectory() as tmp:
        np.save(os.path.join(tmp, "descriptors.npy"), descs)
        np.savez_compressed(
            os.path.join(tmp, "metadata.npz"),
            lats=lats,
            lons=lons,
            headings=headings,
            panoids=panoids,
            paths=paths,
        )

        with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))
            zf.write(os.path.join(tmp, "descriptors.npy"), "descriptors.npy")
            zf.write(os.path.join(tmp, "metadata.npz"), "metadata.npz")

    print(f"[FIXTURES] Generated synthetic fixture: {bundle_path}")
    print(f"[FIXTURES]   {NUM_ENTRIES} entries, {DESC_DIM}-dim descriptors")
    print(f"[FIXTURES]   Center: ({CENTER_LAT}, {CENTER_LON}), radius: 5km")

    manifest_path = os.path.join(output_dir, "test_fixture_50.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    return bundle_path


if __name__ == "__main__":
    generate_fixtures()
