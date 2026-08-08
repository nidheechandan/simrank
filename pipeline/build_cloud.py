#!/usr/bin/env python3
"""Build a web-ready point cloud from a COLMAP dense PLY.

Trims statistical outliers (which otherwise wreck camera framing), then writes
float32 positions + uint8 colors as raw binary, plus meta.json describing the
*real* scene bounds.
"""
import sys
import os
import json
import numpy as np

PLY_PATH = sys.argv[1]
OUT_DIR = sys.argv[2]
KEEP_PCT = float(sys.argv[3]) if len(sys.argv) > 3 else 99.0


def read_ply(path):
    with open(path, "rb") as f:
        header = []
        while True:
            line = f.readline()
            header.append(line)
            if line.strip() == b"end_header":
                break
        n_vertex = None
        for line in b"".join(header).decode("ascii", errors="replace").splitlines():
            if line.startswith("element vertex"):
                n_vertex = int(line.split()[-1])
        dtype = np.dtype([
            ("x", "<f4"), ("y", "<f4"), ("z", "<f4"),
            ("nx", "<f4"), ("ny", "<f4"), ("nz", "<f4"),
            ("r", "u1"), ("g", "u1"), ("b", "u1"),
        ])
        data = np.fromfile(f, dtype=dtype, count=n_vertex)
    xyz = np.stack([data["x"], data["y"], data["z"]], axis=1).astype(np.float32)
    rgb = np.stack([data["r"], data["g"], data["b"]], axis=1).astype(np.uint8)
    return xyz, rgb


xyz, rgb = read_ply(PLY_PATH)
n_before = len(xyz)
print(f"read {n_before} points")

# --- outlier trim: keep points near the median centroid ---
med = np.median(xyz, axis=0)
d = np.linalg.norm(xyz - med, axis=1)
thresh = np.percentile(d, KEEP_PCT)
mask = d <= thresh
xyz = xyz[mask]
rgb = rgb[mask]
print(f"trimmed to {len(xyz)} points ({100*len(xyz)/n_before:.2f}%), "
      f"distance threshold {thresh:.2f}")

bbox_min = xyz.min(axis=0)
bbox_max = xyz.max(axis=0)
extent = bbox_max - bbox_min
center = (bbox_min + bbox_max) / 2.0
# radius of a sphere enclosing the kept points (for framing + frustum culling)
radius = float(np.linalg.norm(xyz - center, axis=1).max())

# Median nearest-neighbour spacing on a random subset -> sensible default point size.
rng = np.random.default_rng(0)
sub_idx = rng.choice(len(xyz), size=min(20000, len(xyz)), replace=False)
sub = xyz[sub_idx].astype(np.float64)
# brute-force NN within the subset (20k x 20k is fine in chunks)
spacings = []
CH = 2000
for i in range(0, len(sub), CH):
    chunk = sub[i:i+CH]
    dists = np.linalg.norm(chunk[:, None, :] - sub[None, :, :], axis=2)
    np.fill_diagonal(dists[:, i:i+len(chunk)], np.inf)
    spacings.append(dists.min(axis=1))
spacing = float(np.median(np.concatenate(spacings)))

print(f"bbox min={bbox_min}, max={bbox_max}")
print(f"extent={extent}, radius={radius:.3f}")
print(f"median NN spacing (subset estimate) = {spacing:.4f}")

os.makedirs(OUT_DIR, exist_ok=True)
xyz.tofile(os.path.join(OUT_DIR, "positions.bin"))
rgb.tofile(os.path.join(OUT_DIR, "colors.bin"))
with open(os.path.join(OUT_DIR, "meta.json"), "w") as f:
    json.dump({
        "n": int(len(xyz)),
        "n_source": int(n_before),
        "bbox_min": bbox_min.tolist(),
        "bbox_max": bbox_max.tolist(),
        "center": center.tolist(),
        "radius": radius,
        "spacing": spacing,
    }, f, indent=2)

print(f"wrote {OUT_DIR}/positions.bin ({xyz.nbytes/1e6:.1f} MB), "
      f"colors.bin ({rgb.nbytes/1e6:.1f} MB), meta.json")
