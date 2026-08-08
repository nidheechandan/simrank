#!/usr/bin/env python3
"""SimRank Depth-Only Policy Training & ONNX Export Script.

Trains the SimRankDepthPolicy neural network on a synthetic depth navigation
dataset (obstacle avoidance & goal seeking) using PyTorch, then exports the
trained network weights to ONNX format.

Usage:
    python policy/train_policy.py --epochs 15 --out policy/simrank_policy.onnx
"""

import argparse
import os
import sys
import torch
import torch.nn as nn
import torch.optim as optim

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from policy.network import SimRankDepthPolicy


def generate_synthetic_batch(batch_size=32):
    """Generates synthetic depth maps and kinematic state vectors with target actions.
    
    Depth map: 64x64 depth values in range [0.2, 5.0] meters.
    State: [vx, vy, vz, roll, pitch, yaw_rate]
    Action: [thrust, roll_rate, pitch_rate, yaw_rate]
    """
    depth = torch.rand(batch_size, 1, 64, 64) * 4.8 + 0.2
    state = torch.randn(batch_size, 6) * 0.5
    
    # Target action: simple heuristic rule (steer away from close obstacles)
    min_depth_left = depth[:, 0, :, :32].mean(dim=(1, 2))
    min_depth_right = depth[:, 0, :, 32:].mean(dim=(1, 2))
    
    target_yaw = torch.clamp((min_depth_right - min_depth_left) * 0.5, -1.0, 1.0)
    target_thrust = torch.clamp(depth.mean(dim=(1, 2, 3)) * 0.2, 0.0, 1.0)
    target_roll = torch.clamp(state[:, 0] * -0.3, -1.0, 1.0)
    target_pitch = torch.clamp(state[:, 1] * 0.3, -1.0, 1.0)
    
    target_actions = torch.stack([target_thrust, target_roll, target_pitch, target_yaw], dim=1)
    return depth, state, target_actions


def train_policy(epochs=15, batch_size=32, lr=1e-3, export_path="policy/simrank_policy.onnx"):
    print("=" * 60)
    print("       SIMRANK DEPTH-ONLY POLICY PRE-TRAINING LOOP          ")
    print("=" * 60)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    model = SimRankDepthPolicy().to(device)
    optimizer = optim.Adam(model.parameters(), lr=lr)
    criterion = nn.MSELoss()
    
    model.train()
    print(f"Training for {epochs} epochs (Batch Size: {batch_size})...")
    
    for epoch in range(1, epochs + 1):
        running_loss = 0.0
        num_batches = 50
        
        for _ in range(num_batches):
            depth, state, targets = generate_synthetic_batch(batch_size)
            depth, state, targets = depth.to(device), state.to(device), targets.to(device)
            
            optimizer.zero_grad()
            outputs = model(depth, state)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()
            
            running_loss += loss.item()
        
        avg_loss = running_loss / num_batches
        print(f"Epoch [{epoch:02d}/{epochs:02d}] - Loss: {avg_loss:.6f}")
    
    # Save PyTorch checkpoint
    checkpoint_path = "policy/simrank_policy.pth"
    torch.save(model.state_dict(), checkpoint_path)
    print(f"\n[OK] Trained checkpoint saved to '{checkpoint_path}'")
    
    # Export to ONNX
    model.eval()
    dummy_depth = torch.randn(1, 1, 64, 64, device=device)
    dummy_state = torch.randn(1, 6, device=device)
    
    print(f"Exporting trained model to ONNX: '{export_path}'...")
    torch.onnx.export(
        model,
        (dummy_depth, dummy_state),
        export_path,
        export_params=True,
        opset_version=18,
        do_constant_folding=True,
        input_names=["depth", "state"],
        output_names=["action"],
        dynamic_axes={
            "depth": {0: "batch_size"},
            "state": {0: "batch_size"},
            "action": {0: "batch_size"},
        },
    )
    
    file_size_kb = os.path.getsize(export_path) / 1024.0
    print(f"[OK] ONNX export complete! Binary size: {file_size_kb:.2f} KB")
    return model


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train SimRank Depth Policy")
    parser.add_argument("--epochs", type=int, default=15, help="Number of training epochs")
    parser.add_argument("--out", type=str, default="policy/simrank_policy.onnx", help="Output ONNX path")
    args = parser.parse_args()
    
    train_policy(epochs=args.epochs, export_path=args.out)
