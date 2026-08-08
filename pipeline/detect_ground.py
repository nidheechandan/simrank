#!/usr/bin/env python3
"""Detect the floor plane of a COLMAP point cloud and derive a levelling transform.

COLMAP's world frame has an arbitrary orientation, so the reconstruction's "up" is
almost never axis-aligned. Snapping to +/-Y or +/-Z can therefore never level it.
This finds the real ground plane by RANSAC and emits the rotation that takes the
floor normal to three.js +Y, plus the translation that puts the floor at y=0 and
the room centred on the origin.

Writes the result back into meta.json.

    python3 detect_ground.py <dir_with_cloud_positions.json_and_meta.json>
"""
import sys
import os
import json
import numpy as np

D = sys.argv[1]
POS = os.path.join(D, "cloud_positions.json")   # raw float32 xyz
META = os.path.join(D, "meta.json")

meta = json.load(open(META))
pts = np.fromfile(POS, dtype="<f4").reshape(-1, 3).astype(np.float64)
print(f"loaded {len(pts):,} points")

rng = np.random.default_rng(0)
sub = pts[rng.choice(len(pts), size=min(300_000, len(pts)), replace=False)]

radius = float(meta["radius"])
THRESH = radius * 0.006          # plane inlier tolerance, ~5 cm at room scale


def ransac_plane(P, iters=3000, thresh=THRESH):
    """Return (normal, d, inlier_mask) for the plane with most inliers: n·x + d = 0."""
    best = (None, None, None, -1)
    N = len(P)
    for _ in range(iters):
        i = rng.choice(N, size=3, replace=False)
        a, b, c = P[i]
        nrm = np.cross(b - a, c - a)
        norm = np.linalg.norm(nrm)
        if norm < 1e-9:
            continue
        nrm = nrm / norm
        d = -nrm.dot(a)
        dist = np.abs(P @ nrm + d)
        cnt = int((dist < thresh).sum())
        if cnt > best[3]:
            best = (nrm, d, dist < thresh, cnt)
    nrm, d, mask, cnt = best
    # least-squares refit on the inliers
    Q = P[mask]
    ctr = Q.mean(axis=0)
    _, _, Vt = np.linalg.svd(Q - ctr, full_matrices=False)
    nrm = Vt[-1] / np.linalg.norm(Vt[-1])
    d = -nrm.dot(ctr)
    dist = np.abs(P @ nrm + d)
    mask = dist < thresh
    return nrm, d, mask


# --- find the ground: a dominant plane with (almost) all points on one side ---
work = sub.copy()
floor_n = floor_d = None
for attempt in range(5):
    nrm, d, mask = ransac_plane(work)
    signed = sub @ nrm + d
    n_above = float((signed > THRESH).sum())
    n_below = float((signed < -THRESH).sum())
    off = n_above + n_below                  # points NOT lying on the plane
    # One-sidedness must be measured among off-plane points only: a floor can have
    # a huge share of all points lying *on* it, which would otherwise mask the test.
    onesided = (max(n_above, n_below) / off) if off > 0 else 0.0
    frac = float(mask.mean())
    print(f"  plane {attempt}: inliers {frac*100:5.2f}%  above {n_above/len(sub)*100:5.1f}%  "
          f"below {n_below/len(sub)*100:5.1f}%  one-sided {onesided*100:5.1f}%")
    if onesided > 0.90:                      # floor or ceiling
        # orient the normal toward the bulk of the room = "up"
        floor_n = nrm if n_above >= n_below else -nrm
        floor_d = d if n_above >= n_below else -d
        print(f"  -> ground plane accepted on attempt {attempt} "
              f"({frac*100:.1f}% of points lie on it)")
        break
    # it was a wall: drop its inliers and look again
    wall_mask = np.abs(work @ nrm + d) < THRESH
    work = work[~wall_mask]
    if len(work) < 5000:
        break

if floor_n is None:
    raise SystemExit("could not identify a ground plane — inspect the cloud manually")

# --- rotation taking floor normal -> three.js up (+Y) ---
up = np.array([0.0, 1.0, 0.0])
v = np.cross(floor_n, up)
s = np.linalg.norm(v)
c = float(floor_n.dot(up))
if s < 1e-9:
    R = np.eye(3) if c > 0 else np.diag([1.0, -1.0, -1.0])
else:
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    R = np.eye(3) + vx + vx @ vx * ((1 - c) / (s ** 2))

tilt_deg = float(np.degrees(np.arccos(np.clip(c, -1, 1))))
print(f"floor normal {floor_n.round(4)}  -> tilt from +Y: {tilt_deg:.2f} deg")

# --- centre horizontally, put floor at y=0 ---
centroid = pts.mean(axis=0)
rot = (pts - centroid) @ R.T
floor_y = float(np.percentile(rot[:, 1], 0.5))     # robust floor level
ceil_y = float(np.percentile(rot[:, 1], 99.5))
height_units = ceil_y - floor_y
post = np.array([-np.median(rot[:, 0]), -floor_y, -np.median(rot[:, 2])])

print(f"height (floor->ceiling) = {height_units:.3f} COLMAP units")
print(f"  -> if the real room is 3.0 m tall, scale = {3.0/height_units:.4f} m/unit")

# quaternion (x, y, z, w) from R
t = np.trace(R)
if t > 0:
    S = np.sqrt(t + 1.0) * 2
    qw, qx, qy, qz = 0.25 * S, (R[2, 1] - R[1, 2]) / S, (R[0, 2] - R[2, 0]) / S, (R[1, 0] - R[0, 1]) / S
elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
    S = np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
    qw, qx, qy, qz = (R[2, 1] - R[1, 2]) / S, 0.25 * S, (R[0, 1] + R[1, 0]) / S, (R[0, 2] + R[2, 0]) / S
elif R[1, 1] > R[2, 2]:
    S = np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
    qw, qx, qy, qz = (R[0, 2] - R[2, 0]) / S, (R[0, 1] + R[1, 0]) / S, 0.25 * S, (R[1, 2] + R[2, 1]) / S
else:
    S = np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
    qw, qx, qy, qz = (R[1, 0] - R[0, 1]) / S, (R[0, 2] + R[2, 0]) / S, (R[1, 2] + R[2, 1]) / S, 0.25 * S

meta["level"] = {
    "pre_translate": (-centroid).tolist(),        # applied before rotation
    "quat_xyzw": [float(qx), float(qy), float(qz), float(qw)],
    "post_translate": post.tolist(),              # applied after rotation
    "floor_normal_colmap": floor_n.tolist(),
    "tilt_deg": tilt_deg,
    "height_units": float(height_units),
}
json.dump(meta, open(META, "w"), indent=2)
print(f"updated {META}")
