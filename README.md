# SimRank — UWB Ground-Truth Rig + Room Reconstruction & Policy Framework

**Team Akshastra · Neurobots Championship 2026**

A low-cost motion-capture replacement (7-anchor UWB) fused with COLMAP dense 3D room reconstruction, live WebGL drone position overlay, depth-only policy execution framework, and empirical sim-to-real validation tools.

See [`docs/plan.md`](docs/plan.md) for the full 24-hour design architecture and [`docs/limitations.md`](docs/limitations.md) for explicit engineering boundaries.

**Live Viewer:** [https://simrank-room-scan.vercel.app](https://simrank-room-scan.vercel.app)

---

## End-to-End System Architecture

```
DWM3001CDK tag ──(FiRa DS-TWR, 7 anchors)──► Jetson Orin Nano
                                                 │
                                    uwb_listener.py   parses raw ranging blocks -> JSONL
                                                 │
                                    trilaterate.py     2D closed-form multilateration
                                                 │
                               ┌─────────────────┴─────────────────┐
                    dashboard_local.py                   jetson_publisher.py
                    (local viewer, :8080)                 (+ Pixhawk MAVLink attitude)
                                                                   │
                                                         POST /api/position (x-api-key)
                                                                   ▼
                                                    Vercel API Relay & WebGL Viewer
                                                                   │
                                                         [⚡ RunPod GPU Worker Trigger]
                                                                   ▼
                                                    COLMAP / 3D Gaussian Splat Pipeline
```

---

## Repository Layout

```
index.html                  Live 3D viewer (Three.js WebGL, live drone overlay & RunPod trigger)
api/
  position.js               Vercel serverless relay with x-api-key publisher authentication
  trigger_pipeline.js       Serverless GPU reconstruction job dispatch & status queue
anchors.json                Surveyed 7-anchor metric positions (UWB frame)
meta.json                   Point cloud metadata + auto-detected ground-plane transform
cloud_positions.json        Point cloud binary float32 positions (58.5 MB)
cloud_colors.json           Point cloud binary uint8 colors (15.3 MB)

policy/
  network.py                PyTorch Depth-Only Policy Network (1x1x64x64 depth + 1x6 state -> 1x4 action)
  export_onnx.py            ONNX Exporter script supporting dynamic batch size & FP16 precision
  verify_inference.py       Dynamic tensor flow & signature verification tool

data/
  uwb_eval_dataset.csv      Empirical UWB touchpoint dataset (N=25 surveyed reference points)

pipeline/
  analyze_uwb_accuracy.py   Calculates 2D/3D RMSE, MAE, P95 & Noise-Floor divergence ratio (>2x test)
  eval_depth_gap.py         Evaluates depth domain gap between gsplat mesh and D415 IR sensor model
  runpod_worker.py          GPU worker pipeline orchestrator for dense COLMAP / GSplat jobs
  build_cloud.py            Trims PLY outliers and exports web-ready binary point clouds
  detect_ground.py          RANSAC ground-plane detection and auto-leveling transform matrix

jetson/
  uwb_listener.py           Parses DWM3001CDK CLI ranging output -> JSONL
  trilaterate.py            Linear closed-form multilateration solver
  dashboard_local.py        Local standalone Flask viewer
  jetson_publisher.py       Puses live UWB + MAVLink attitude to Vercel API with auth headers
  install.sh                Idempotent systemd installation script

docs/
  plan.md                   Full 24-hour R2S2R validation design doc
  limitations.md            Honest engineering state & bounds
```

---

## Key Technical Milestones & Empirical Results

### 1. Empirical UWB Accuracy Benchmark (`pipeline/analyze_uwb_accuracy.py`)
- **Sample Size**: N = 25 reference points across a 3.5m x 2.5m arena. *(Note: This dataset is synthetically generated to model DW1000 error distribution and multipath effects for this prototype, rather than physically captured).*
- **2D Position RMSE**: **12.12 cm**
- **Noise-Floor-Relative Divergence**: **2.52x** (Target > 2.0x local stationary UWB noise floor of 4.8 cm RMS).

### 2. Depth-Only Policy Network & ONNX Export (`policy/`)
- **Input Tensors**:
  - `depth`: `[Batch, 1, 64, 64]` normalized depth map (meters).
  - `state`: `[Batch, 6]` kinematic state `[vx, vy, vz, roll, pitch, yaw_rate]`.
- **Output Tensor**:
  - `action`: `[Batch, 4]` normalized thrust and attitude rate commands `[-1.0, 1.0]`.
- **Export Status**: A full, valid ONNX graph export (untrained, random weights) is committed (`policy/simrank_policy.onnx`, 25 KB).
- **Precision Rationale**: FP16 precision choice avoids INT8 quantization noise corrupting sim-to-real gap metrics.

### 3. Secured Vercel Relay & RunPod GPU Worker Integration (`api/`)
- **API Security**: `POST /api/position` enforces `x-api-key` authorization headers.
- **Pipeline Orchestration**: Web UI triggers COLMAP / 3D Gaussian Splatting jobs via `POST /api/trigger_pipeline`, returning job IDs and polling progress.

### 4. Depth Domain Gap Evaluation (`pipeline/eval_depth_gap.py`)
- Evaluates synthetic COLMAP/GSplat depth against an Intel RealSense D415 IR noise model ($0.002 \cdot z^2 + 0.005$).
- *(Note: Uses simulated noise applied to synthetic poses, not live hardware captures).*

---

## Verification & Execution Commands

```bash
# 1. Run UWB Empirical Accuracy & Noise Floor Analysis
python pipeline/analyze_uwb_accuracy.py

# 2. Run Depth Sensor Domain Gap Evaluation
python pipeline/eval_depth_gap.py

# 3. Export Policy Network to ONNX
python policy/export_onnx.py

# 4. Verify Policy ONNX Tensor Signature & Dynamic Batching
python policy/verify_inference.py

# 5. Test Local Web Viewer
python3 -m http.server 8000
```
