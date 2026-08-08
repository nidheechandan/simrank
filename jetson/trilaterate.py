#!/usr/bin/env python3
"""Live multilateration engine for the DWM3001CDK UWB rig.

Tails uwb_ranging.jsonl (written by uwb_listener.py), loads surveyed anchor
positions, and solves for the tag's live (x, y, z) via least-squares
multilateration on every ranging block. Publishes the latest solution to a
small JSON state file that dashboard.py serves over HTTP.

No clock sync needed: FiRa TWR already returns metric distance per anchor,
not TDOA, so this is plain trilateration, not multilateration-with-bias.
"""
import json
import time
import os
import sys
import numpy as np
from scipy.optimize import least_squares

LOG_PATH = "/home/anupamsoni/uwb_ranging.jsonl"
ANCHORS_PATH = "/home/anupamsoni/anchor_positions.json"
STATE_PATH = "/home/anupamsoni/tag_position_state.json"
MIN_ANCHORS = 3

# Anchors are coplanar (all surveyed at the same height), which makes a full
# 3D solve for height unreliable (see plan Gate 4). We fix the tag's assumed
# height equal to the anchors' height, which means the (z - z_i) term is
# identically zero for every anchor -- this is exactly the classic 2D
# trilateration problem, which has a robust closed-form LINEAR solution
# (subtract the first anchor's distance equation from every other anchor's
# to cancel the quadratic term). We use that instead of an iterative
# nonlinear solver, which can converge to the wrong local minimum when
# warm-started from a noisy previous estimate.
TAG_Z_M = 0.32


def load_anchors():
    with open(ANCHORS_PATH) as f:
        raw = json.load(f)
    return {int(k): np.array(v, dtype=float) for k, v in raw.items()}


def solve_position(anchor_pts, distances_m):
    """anchor_pts: list of np.array([x,y,z]) (z assumed equal for all, cancels out);
    distances_m: matching list of measured distances in metres.
    Closed-form 2D linear multilateration, globally optimal for the linearized
    system -- no initial guess, no local-minimum risk."""
    anchor_pts = np.array(anchor_pts)
    distances_m = np.array(distances_m)
    xy = anchor_pts[:, :2]

    x1, y1 = xy[0]
    d1 = distances_m[0]
    A = 2 * (xy[1:] - np.array([x1, y1]))
    b = (x1 ** 2 - xy[1:, 0] ** 2) + (y1 ** 2 - xy[1:, 1] ** 2) + distances_m[1:] ** 2 - d1 ** 2

    (x, y), *_ = np.linalg.lstsq(A, b, rcond=None)
    pos = np.array([x, y, TAG_Z_M])

    resid = np.linalg.norm(anchor_pts - pos, axis=1) - distances_m
    resid_rms = float(np.sqrt(np.mean(resid ** 2)))
    return pos, resid_rms


def follow(path):
    """Generator yielding new lines appended to `path`, like `tail -f`."""
    while not os.path.exists(path):
        time.sleep(1)
    f = open(path, "r")
    f.seek(0, os.SEEK_END)
    while True:
        line = f.readline()
        if not line:
            time.sleep(0.05)
            continue
        yield line


def main():
    anchors = load_anchors()
    print(f"loaded {len(anchors)} anchor positions: {list(anchors.keys())}", flush=True)

    anchors_mtime = os.path.getmtime(ANCHORS_PATH)

    for line in follow(LOG_PATH):
        # hot-reload anchor positions if the survey file changes (Step 1 finishing late)
        try:
            mtime = os.path.getmtime(ANCHORS_PATH)
            if mtime != anchors_mtime:
                anchors = load_anchors()
                anchors_mtime = mtime
                print(f"reloaded anchor positions: {list(anchors.keys())}", flush=True)
        except OSError:
            pass

        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue

        pts, dists, used = [], [], []
        for addr_str, meas in rec.get("measurements", {}).items():
            addr = int(addr_str)
            if meas.get("status") != "SUCCESS" or meas.get("distance_cm") is None:
                continue
            if addr not in anchors:
                continue
            pts.append(anchors[addr])
            dists.append(meas["distance_cm"] / 100.0)
            used.append(addr)

        if len(pts) < MIN_ANCHORS:
            continue

        pos, resid_rms = solve_position(pts, dists)

        state = {
            "t": rec.get("ts"),
            "block_index": rec.get("block_index"),
            "tag": [round(float(v), 3) for v in pos],
            "residual_cm": round(resid_rms * 100.0, 1),
            "anchors_used": used,
            "anchors": {str(k): list(v) for k, v in anchors.items()},
        }
        tmp_path = STATE_PATH + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(state, f)
        os.replace(tmp_path, STATE_PATH)


if __name__ == "__main__":
    main()
