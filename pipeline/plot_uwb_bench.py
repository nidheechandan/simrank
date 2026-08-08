#!/usr/bin/env python3
"""SimRank UWB Accuracy Visualizer & Performance Benchmarking Tool.

Generates ASCII scatter maps, error percentile plots, and detailed covariance
summaries from empirical touchpoint data in data/uwb_eval_dataset.csv.

Usage:
    python pipeline/plot_uwb_bench.py
"""

import csv
import math
import os
import sys
import numpy as np


def render_ascii_scatter(gt_coords, est_coords, grid_w=40, grid_h=15):
    """Renders ASCII 2D spatial scatter plot showing GT vs Estimated positions."""
    grid = [[" " for _ in range(grid_w)] for _ in range(grid_h)]
    
    max_x, max_y = 3.5, 4.0
    
    # Draw arena border
    for r in range(grid_h):
        grid[r][0] = "|"
        grid[r][grid_w - 1] = "|"
    for c in range(grid_w):
        grid[0][c] = "-"
        grid[grid_h - 1][c] = "-"
    grid[0][0] = "+"
    grid[0][grid_w - 1] = "+"
    grid[grid_h - 1][0] = "+"
    grid[grid_h - 1][grid_w - 1] = "+"

    # Plot points: '+' = Ground Truth, '*' = Estimate
    for (gx, gy), (ex, ey) in zip(gt_coords, est_coords):
        gc = int(np.clip(gx / max_x * (grid_w - 3) + 1, 1, grid_w - 2))
        gr = int(np.clip(gy / max_y * (grid_h - 3) + 1, 1, grid_h - 2))
        ec = int(np.clip(ex / max_x * (grid_w - 3) + 1, 1, grid_w - 2))
        er = int(np.clip(ey / max_y * (grid_h - 3) + 1, 1, grid_h - 2))
        
        grid[gr][gc] = "O"  # GT point
        grid[er][ec] = "x"  # Estimate point
        
    print("\n--- 2D Spatial Scatter Map (O = Ground Truth, x = UWB Estimate) ---")
    for row in grid:
        print("".join(row))
    print("---------------------------------------------------------------------")


def generate_benchmark_report(dataset_path="data/uwb_eval_dataset.csv"):
    if not os.path.exists(dataset_path):
        print(f"[Error] Dataset '{dataset_path}' not found.")
        sys.exit(1)

    gt_coords = []
    est_coords = []
    errors = []

    with open(dataset_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            gx, gy = float(row["gt_x_m"]), float(row["gt_y_m"])
            ex, ey = float(row["est_x_m"]), float(row["est_y_m"])
            err = float(row["err_2d_cm"])
            gt_coords.append((gx, gy))
            est_coords.append((ex, ey))
            errors.append(err)

    errors = np.array(errors)
    rmse = np.sqrt(np.mean(errors ** 2))
    mae = np.mean(errors)
    p50 = np.percentile(errors, 50)
    p95 = np.percentile(errors, 95)
    std_dev = np.std(errors)

    print("=" * 65)
    print("      SIMRANK UWB BENCHMARK & PRECISION PERFORMANCE REPORT      ")
    print("=" * 65)
    print(f"Total Touchpoint Touch-tests (N):  {len(errors)} surveyed points")
    print(f"2D Position RMSE:                  {rmse:.2f} cm")
    print(f"2D Mean Absolute Error (MAE):     {mae:.2f} cm")
    print(f"Error Standard Deviation (Std):   {std_dev:.2f} cm")
    print(f"50th Percentile Error (P50):       {p50:.2f} cm")
    print(f"95th Percentile Error (P95):       {p95:.2f} cm")
    print("-" * 65)

    render_ascii_scatter(gt_coords, est_coords)
    print("[OK] Benchmark report and ASCII scatter visualization completed successfully.")


if __name__ == "__main__":
    generate_benchmark_report()
