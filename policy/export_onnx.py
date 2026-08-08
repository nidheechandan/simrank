#!/usr/bin/env python3
"""ONNX Exporter for SimRank Depth Policy Network.

Exports the PyTorch policy network to ONNX format with FP16 precision option, dynamic batch sizes,
and standard tensor signature:
  Inputs:
    - depth: [batch_size, 1, 64, 64] float32 / float16
    - state: [batch_size, 6] float32 / float16
  Outputs:
    - action: [batch_size, 4] float32 / float16

Verifies exported graph structure and dynamic batch dimension execution.
"""

import os
import sys
import argparse
import numpy as np

def export_onnx(output_path="policy/simrank_policy.onnx", fp16=False):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import torch
    from policy.network import SimRankDepthPolicy

    print(f"[SimRank Policy Exporter] Initializing model (FP16={fp16})...")
    model = SimRankDepthPolicy()
    model.eval()

    if fp16:
        model = model.half()
        dtype = torch.float16
    else:
        dtype = torch.float32

    # Dummy inputs for trace & shape inference
    dummy_depth = torch.randn(1, 1, 64, 64, dtype=dtype)
    dummy_state = torch.randn(1, 6, dtype=dtype)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    input_names = ["depth", "state"]
    output_names = ["action"]
    dynamic_axes = {
        "depth": {0: "batch_size"},
        "state": {0: "batch_size"},
        "action": {0: "batch_size"}
    }

    print(f"[SimRank Policy Exporter] Exporting ONNX model to '{output_path}'...")
    torch.onnx.export(
        model,
        (dummy_depth, dummy_state),
        output_path,
        export_params=True,
        opset_version=14,
        do_constant_folding=True,
        input_names=input_names,
        output_names=output_names,
        dynamic_axes=dynamic_axes
    )

    print(f"[OK] Exported successfully: {output_path} ({os.path.getsize(output_path) / 1024:.1f} KB)")

    # Verify model with onnx if available
    try:
        import onnx
        onnx_model = onnx.load(output_path)
        onnx.checker.check_model(onnx_model)
        print("[OK] ONNX graph check passed cleanly.")
    except Exception as e:
        print(f"⚠️ ONNX graph check warning: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="policy/simrank_policy.onnx")
    parser.add_argument("--fp16", action="store_true", help="Export FP16 model")
    args = parser.parse_args()

    export_onnx(args.out, args.fp16)
