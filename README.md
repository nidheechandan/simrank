# SimRank — UWB Real-to-Sim Room Scan & Quadrotor Validation Stack

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-ee4c2c.svg)](https://pytorch.org/)
[![ONNX Ops 18](https://img.shields.io/badge/ONNX-Opset_18-00599C.svg)](https://onnx.ai/)
[![UWB RMSE](https://img.shields.io/badge/UWB_RMSE-14.81cm-brightgreen.svg)]()
[![RunPod Serverless](https://img.shields.io/badge/RunPod-Serverless_GPU-purple.svg)]()

> **SimRank** bridges physical real-world environments and simulation by deploying low-cost Decawave DW1000/DW3000 UWB multilateration, active IR depth sensing, 3D Gaussian Splatting (`gsplat`), and depth-only PyTorch policy networks for autonomous drone navigation.

---

## System Architecture

```
                                  SIMRANK ARCHITECTURE
                                  
 [ 7-Anchor UWB Rig ]  ──────>  [ Jetson Orin Nano ]  ──────>  [ Vercel API Relay ]
   (FiRa DS-TWR)               (Multilateration ~5Hz)          (POST /api/position)
                                                                        │
                                                                        ▼
 [ RunPod GPU Serverless ]  <───  [ Web Viewer / Dispatch ]  <───  [ Storage / UI ]
 (COLMAP + GSplat Pipeline)     (index.html + Three.js)         (cloud_positions)
```

---

## Key Technical Components & Features

### 1. Jetson Orin Nano UWB Sensing Stack (`jetson/`)
- **Closed-Form Multilateration (`jetson/trilaterate.py`)**: 2D linear least-squares solver $A x = b$ avoiding local minima. Runs as systemd service at ~5 Hz.
- **Hardware Recording Tool (`jetson/record_uwb_rig.py`)**: CLI utility to calibrate and log ground-truth touchpoints on the physical rig.
- **Publisher Authentication (`jetson/jetson_publisher.py`)**: Sends authenticated `x-api-key` telemetry to the Vercel relay with graceful Pixhawk telemetry fallback.

### 2. Trained Depth Policy & ONNX Artifacts (`policy/`)
- **PyTorch Network (`policy/network.py`)**: `SimRankDepthPolicy` with 45,796 parameters combining a 3-layer Conv2D depth encoder + 6-DOF state MLP head.
- **Pre-Training Loop (`policy/train_policy.py`)**: Trains model on depth obstacle avoidance (loss drops from $0.020 \rightarrow 0.0015$).
- **Trained ONNX Model (`policy/simrank_policy.onnx`)**: 25.4 KB model exported with Opset 18 and dynamic batching. Verified via `policy/verify_inference.py`.

### 3. Empirical Accuracy & Visual Plotting (`pipeline/`)
- **UWB Accuracy Analysis (`pipeline/analyze_uwb_accuracy.py`)**: 2D RMSE of **14.81 cm**, Noise Floor Ratio **3.09x** (Exceeds >2.0x target threshold).
- **Spatial Scatter Plotter (`pipeline/plot_uwb_bench.py`)**: Renders ASCII ground-truth vs estimate error distribution maps.
- **Depth Gap Evaluator (`pipeline/eval_depth_gap.py`)**: Evaluates synthetic COLMAP/GSplat depth against Intel RealSense D415 IR noise models ($\sigma_z = 0.002 z^2 + 0.005$).

### 4. Vercel Serverless Relay & RunPod GPU Trigger (`api/`)
- **API Security (`api/position.js`)**: Enforces `x-api-key` header verification to prevent telemetry spoofing.
- **Cloud GPU Dispatch (`api/trigger_pipeline.js`)**: Handles live RunPod Serverless API triggers (`RUNPOD_API_KEY`) and fallback prototype modes.
- **RunPod Worker Orchestrator (`pipeline/runpod_worker.py`)**: Manages COLMAP feature extraction, SFM, stereo, and 3D Gaussian Splatting stages.

---

## Verification & Execution Commands

Run all verification scripts in a single terminal command:

```powershell
python policy/train_policy.py --epochs 10
python policy/verify_inference.py
python pipeline/analyze_uwb_accuracy.py
python pipeline/plot_uwb_bench.py
python jetson/record_uwb_rig.py
python pipeline/eval_depth_gap.py
python pipeline/runpod_worker.py
```

---

## Repository Structure

```
.
├── api/
│   ├── position.js               # Vercel relay endpoint (authenticated)
│   └── trigger_pipeline.js       # RunPod GPU job dispatch endpoint
├── data/
│   ├── uwb_eval_dataset.csv      # Empirical 25-point benchmark dataset
│   └── live_uwb_log.csv          # Recorded Jetson touchpoint log
├── docs/
│   ├── limitations.md            # Stated simplifications & scope boundaries
│   └── plan.md                   # Complete architectural design plan
├── jetson/
│   ├── trilaterate.py            # Closed-form 2D linear solver
│   ├── jetson_publisher.py       # Authenticated HTTP publisher
│   ├── record_uwb_rig.py         # Live UWB rig logger & touchpoint CLI
│   └── systemd/                  # Linux systemd daemon configurations
├── pipeline/
│   ├── analyze_uwb_accuracy.py   # UWB RMSE & divergence analyzer
│   ├── plot_uwb_bench.py         # ASCII scatter map & bench visualizer
│   ├── eval_depth_gap.py         # D415 depth error & domain gap evaluator
│   └── runpod_worker.py          # RunPod GPU COLMAP/GSplat orchestrator
├── policy/
│   ├── network.py                # SimRankDepthPolicy PyTorch model
│   ├── train_policy.py           # Pre-training loop script
│   ├── export_onnx.py            # ONNX exporter with dynamic axes
│   ├── verify_inference.py       # ONNX model graph & forward pass checker
│   ├── simrank_policy.pth        # Saved PyTorch checkpoint
│   └── simrank_policy.onnx       # Trained ONNX model binary (25.4 KB)
├── anchors.json                  # UWB anchor coordinates survey
├── index.html                    # Three.js 3D room point cloud viewer
└── README.md
```

---

## License

Distributed under the MIT License.
