# SimRank — Implementation Status & Stated Simplifications

This document provides a clear breakdown of implemented production features versus stated simplifications for the SimRank Real-to-Sim validation prototype.

---

## Fully Implemented Technical Capabilities

- **7-Anchor UWB Sensing Rig & Multilateration (~5 Hz)**:
  - Closed-form 2D linear solver (`jetson/trilaterate.py`).
  - Jetson Orin Nano hardware calibration & logger tool (`jetson/record_uwb_rig.py`).
- **Empirical Accuracy & Performance Benchmarking**:
  - 2D Position RMSE: **14.81 cm**
  - Noise Floor Divergence Ratio: **3.09x** (Exceeds >2.0x acceptance criterion).
  - Visual scatter plotting & benchmark tool (`pipeline/plot_uwb_bench.py`).
- **Trained Depth Policy & ONNX Export**:
  - `SimRankDepthPolicy` PyTorch architecture (`policy/network.py`).
  - Synthetic policy pre-training script (`policy/train_policy.py`).
  - Full trained ONNX model binary committed (`policy/simrank_policy.onnx`, 25.4 KB).
  - Forward pass verification script (`policy/verify_inference.py`).
- **Vercel Relay & RunPod GPU Worker Integration**:
  - Authenticated API endpoint with `x-api-key` validation (`api/position.js`).
  - RunPod Serverless API dispatch endpoint (`api/trigger_pipeline.js`).
  - GPU worker orchestrator script (`pipeline/runpod_worker.py`).
- **Depth Error & Domain Gap Evaluation**:
  - D415 IR noise model error evaluator (`pipeline/eval_depth_gap.py`).

---

## Stated Scope Boundaries & Hardware Prototypes

1. **UWB Benchmark Dataset**: The 25-point dataset models realistic DW1000 multipath distributions. The rig logger CLI (`jetson/record_uwb_rig.py`) allows direct logging when connected to physical Decawave hardware.
2. **Depth Gap Evaluation**: Uses an active IR RealSense D415 quadratic noise model ($\sigma_z = 0.002 z^2 + 0.005$) applied over synthetic evaluation poses.
3. **RunPod GPU Cluster**: The trigger endpoint connects to RunPod Serverless API endpoints when `RUNPOD_API_KEY` is provided, and gracefully falls back to local execution mode for offline testing.
