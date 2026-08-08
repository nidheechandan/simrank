#!/usr/bin/env python3
"""SimRank Depth-Only Policy Network for Sim-to-Real Drone Navigation.

Architecture:
  - Input 1: Depth image tensor [Batch, 1, 64, 64] (meters, normalized)
  - Input 2: Kinematic state tensor [Batch, 6] (vx, vy, vz, roll, pitch, yaw_rate)
  - CNN Feature Extractor: 3 Conv2d layers with BatchNorm + LeakyReLU + AdaptiveAvgPool2d
  - State Fusion: Concatenates 64-dim CNN latent with 6-dim kinematic vector (70-dim joint embedding)
  - Policy Head: MLP (70 -> 128 -> 64 -> 4) outputting [thrust, roll_cmd, pitch_cmd, yaw_rate_cmd]

Insulated from photometric domain shift by operating exclusively on normalized depth maps.
Quantization rationale: Exported in FP16 precision to avoid INT8 discretization noise corrupting
the sim-to-real gap measurement.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

class DepthEncoder(nn.Module):
    """Convolutional encoder converting 1x64x64 depth frames into a 64-dim latent representation."""
    def __init__(self, latent_dim: int = 64):
        super().__init__()
        self.conv1 = nn.Conv2d(1, 16, kernel_size=5, stride=2, padding=2)  # -> 16 x 32 x 32
        self.bn1 = nn.BatchNorm2d(16)
        self.conv2 = nn.Conv2d(16, 32, kernel_size=3, stride=2, padding=1) # -> 32 x 16 x 16
        self.bn2 = nn.BatchNorm2d(32)
        self.conv3 = nn.Conv2d(32, 64, kernel_size=3, stride=2, padding=1) # -> 64 x 8 x 8
        self.bn3 = nn.BatchNorm2d(64)
        self.pool = nn.AdaptiveAvgPool2d((1, 1))                           # -> 64 x 1 x 1
        self.fc = nn.Linear(64, latent_dim)

    def forward(self, depth: torch.Tensor) -> torch.Tensor:
        x = F.leaky_relu(self.bn1(self.conv1(depth)), 0.1)
        x = F.leaky_relu(self.bn2(self.conv2(x)), 0.1)
        x = F.leaky_relu(self.bn3(self.conv3(x)), 0.1)
        x = self.pool(x)
        x = torch.flatten(x, 1)
        x = self.fc(x)
        return x

class SimRankDepthPolicy(nn.Module):
    """End-to-end Sim-to-Real policy network combining depth observation and vehicle state."""
    def __init__(self, state_dim: int = 6, action_dim: int = 4, latent_dim: int = 64):
        super().__init__()
        self.depth_encoder = DepthEncoder(latent_dim=latent_dim)
        
        joint_dim = latent_dim + state_dim  # 64 + 6 = 70
        self.fc1 = nn.Linear(joint_dim, 128)
        self.bn_mlp = nn.BatchNorm1d(128)
        self.fc2 = nn.Linear(128, 64)
        self.action_head = nn.Linear(64, action_dim)
        
    def forward(self, depth: torch.Tensor, state: torch.Tensor) -> torch.Tensor:
        """Forward pass.
        
        Args:
            depth: Tensor of shape [Batch, 1, 64, 64]
            state: Tensor of shape [Batch, 6] (vx, vy, vz, roll, pitch, yaw_rate)
            
        Returns:
            action: Tensor of shape [Batch, 4] (normalized control commands in [-1, 1])
        """
        depth_latent = self.depth_encoder(depth)
        joint_state = torch.cat([depth_latent, state], dim=1)
        
        x = F.leaky_relu(self.bn_mlp(self.fc1(joint_state)), 0.1)
        x = F.leaky_relu(self.fc2(x), 0.1)
        action = torch.tanh(self.action_head(x))
        return action

if __name__ == "__main__":
    model = SimRankDepthPolicy()
    model.eval()
    dummy_depth = torch.randn(1, 1, 64, 64)
    dummy_state = torch.randn(1, 6)
    out = model(dummy_depth, dummy_state)
    print(f"Policy model instantiated successfully.")
    print(f"Input depth shape: {dummy_depth.shape}")
    print(f"Input state shape: {dummy_state.shape}")
    print(f"Output action shape: {out.shape} -> {out.detach().numpy()}")
