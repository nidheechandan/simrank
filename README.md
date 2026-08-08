# SimRank — UWB Ground-Truth Rig + Room Reconstruction

**Team Akashastra · Neurobots Championship 2026**

A low-cost motion-capture replacement (7-anchor UWB) fused with a COLMAP dense
reconstruction, served as a live 3D viewer with a real, moving drone position
overlaid on the real room. Part of a larger sim-to-real (R2S2R) validation
plan — see [`docs/plan.md`](docs/plan.md) for the full 24-hour design and
[`docs/limitations.md`](docs/limitations.md) for what is *not* built yet,
stated plainly rather than discovered by a reviewer.

**Live:** https://simrank-room-scan.vercel.app

---

## What's actually running

```
DWM3001CDK tag ──(FiRa DS-TWR, 7 anchors)──► Jetson Orin Nano
                                                 │
                                    uwb_listener.py   parses raw ranging
                                                 │      blocks -> JSONL
                                    trilaterate.py     2-D closed-form
                                                 │      multilateration
                              ┌──────────────────┴──────────────────┐
                    dashboard_local.py                    jetson_publisher.py
                    (local, no internet needed)            (+ Pixhawk MAVLink
                    http://<jetson-ip>:8080                 attitude, when
                                                              connected)
                                                                    │
                                                          POST /api/position
                                                                    ▼
                                                     Vercel-hosted viewer
                                                     (this repo's index.html)
```

Everything upstream of `jetson_publisher.py` is hardware-verified: 7 anchors +
1 tag, battery-powered, NVM-persisted role config, running as systemd services
on the Jetson. `jetson_publisher.py` additionally reads Pixhawk `ATTITUDE`
MAVLink messages so the viewer can render an *oriented* drone, not just a
position dot — but degrades cleanly to position-only if no flight controller
is connected (see `jetson/jetson_publisher.py` docstring).

## Repo layout

```
index.html              Live 3D viewer (three.js, ES modules, no build step)
api/position.js          Vercel serverless relay: Jetson POSTs, viewer polls
anchors.json              Surveyed anchor positions (metric UWB frame)
meta.json                 Point-cloud metadata + auto-detected ground-plane
cloud_positions.json      Point cloud, raw float32 (renamed .json — see note)
cloud_colors.json         Point cloud color, raw uint8 (renamed .json — see note)

jetson/
  uwb_listener.py         Parses DWM3001CDK CLI ranging output -> JSONL
  trilaterate.py           JSONL -> live (x,y) via closed-form multilateration
  dashboard_local.py        Local Flask viewer (works with no internet)
  jetson_publisher.py       Fuses UWB position + Pixhawk attitude, pushes live
  systemd/*.service          Unit templates (placeholders filled by install.sh)
  install.sh                One command to bring the whole Jetson pipeline up

pipeline/
  build_cloud.py           COLMAP PLY -> trimmed, web-ready binary point cloud
  detect_ground.py          RANSAC ground-plane detection + auto-level solve

docs/
  plan.md                   Full R2S2R hackathon plan
  limitations.md             What's not built, stated up front
```

### Why raw point-cloud data is named `.json`

`cloud_positions.json` / `cloud_colors.json` are raw binary buffers
(`float32` XYZ, `uint8` RGB) — not actually JSON. This is deliberate: served
as `.bin` with `application/octet-stream`, download-manager browser
extensions (IDM etc.) intercept the `fetch()` as a file download and the
viewer silently gets nothing. Serving the same bytes under a `.json` name
sidesteps that. `index.html` reads them as raw `ArrayBuffer`s, not `JSON.parse`.

## Running it

**Viewer only** (no hardware): any static file server —
```
python3 -m http.server 8000
```

**Full Jetson pipeline** (tag + anchors + optional Pixhawk):
```
git clone https://github.com/TheOnlyOne001/SimRack.git ~/simrank
cd ~/simrank/jetson && ./install.sh
```
`install.sh` is idempotent — installs missing Python deps, seeds
`anchor_positions.json` from `anchors.json` if not already present, installs
and starts four chained `systemd` services (`uwb-listener` →
`uwb-trilaterate` → `uwb-dashboard` / `uwb-publisher`), and prints both the
local and hosted viewer URLs.

**Rebuilding the point cloud** from a COLMAP dense PLY:
```
python3 pipeline/build_cloud.py path/to/fused.ply <out_dir> [max_points]
python3 pipeline/detect_ground.py <out_dir>   # adds the auto-level transform
```

## Known, stated simplifications

- Jetson data-file paths (`uwb_listener.py`, `trilaterate.py`,
  `jetson_publisher.py`) are hardcoded to `/home/anupamsoni/...` — this
  rig's actual provisioned user. Correct and tested for this single device;
  would need parameterizing for a fleet.
- COLMAP → UWB metric registration is a manually-tuned similarity transform
  (`DEFAULT_REG` in `index.html`), not solved from correspondences. See
  `docs/limitations.md`.
- All 7 UWB anchors are coplanar (z = 0.32 m), so height is not independently
  observable — the solver fixes z and runs a closed-form 2-D solve. This is
  documented in `anchors.json` and discussed in `docs/limitations.md`.

See `docs/limitations.md` for the full, deliberately-unhidden list.
