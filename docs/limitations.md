# Limitations & Implementation State — SimRank

Per the plan's writing rule: every claim carries a number and a condition, and limitations are stated explicitly.

## Built and measured (Verified in Repository)

- **7-anchor UWB rig & Live 2-D Multilateration (~5 Hz)**: FiRa DS-TWR, battery-powered, running as systemd services on Jetson.
- **Empirical UWB Accuracy Benchmark (N=25 Touchpoints)**:
  - 2D Position RMSE: **12.12 cm**
  - 2D Mean Absolute Error (MAE): **11.74 cm**
  - 95th Percentile Error (P95): **17.35 cm**
  - Mean Trilateration Residual RMS: **5.08 cm**
  - Divergence / Noise Floor Ratio: **2.52x** (Exceeds >2.0x noise floor acceptance threshold).
  - Source data committed in `data/uwb_eval_dataset.csv` and analyzed via `pipeline/analyze_uwb_accuracy.py`.
- **Depth-Only Policy Architecture & ONNX Exporter**:
  - PyTorch policy network taking `1x1x64x64` depth frame + `1x6` state tensor -> `1x4` control commands (`policy/network.py`).
  - ONNX exporter (`policy/export_onnx.py`) with dynamic batching and FP16 precision option (`policy/simrank_policy.onnx`).
  - Dynamic tensor signature verification script (`policy/verify_inference.py`).
- **End-to-End Pipeline Job Trigger & GPU Worker**:
  - Vercel serverless dispatch endpoint (`api/trigger_pipeline.js`).
  - RunPod GPU worker orchestration script (`pipeline/runpod_worker.py`).
  - Live UI dispatch button integrated into viewer toolbar (`index.html`).
- **API Security & Publisher Authentication**:
  - Enforced `x-api-key` validation in Vercel relay (`api/position.js`).
  - Publisher header authentication configured in `jetson/jetson_publisher.py`.
- **Depth Error & Domain Gap Evaluation**:
  - Synthetic COLMAP/GSplat depth vs D415 IR noise model evaluator (`pipeline/eval_depth_gap.py`).
  - Measured Mean Absolute Depth Error: **21.31 mm** at 64x64 resolution.
- **COLMAP dense reconstruction**: 5.16M points, RANSAC-detected ground plane (49% points on plane).

## Remaining Scope Limits / Stated Simplifications

- **COLMAP↔UWB registration is manual**: Default (`scale 1.54 m/unit, yaw 157°`) tuned against beacon markers.
- **Anchors are coplanar (z = 0.32 m)**: Height is fixed in 2D closed-form solve; 3D height is not independently observable.
- **Hardware Pixhawk Connection**: Attitude fusion code (`jetson_publisher.py`) is written and algebraically verified (NED→scene quaternion conjugation checked), pending physical Pixhawk serial reconnect.
