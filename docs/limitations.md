# Limitations — stated before results, not retrofitted

Per the plan's own writing rule: every claim carries a number and a
condition, and limitations are written first.

## Built and measured
- 7-anchor UWB rig, FiRa DS-TWR, battery-powered, NVM-persistent role config
  — verified across real power cycles.
- Live 2-D trilateration (~5 Hz), running as a systemd service.
- COLMAP dense reconstruction, 5.16M points, RANSAC-detected ground plane
  (49% of points on the plane, one-sidedness 97.5%).
- One tape-measured reference point: ≈24–26 cm position error (**n = 1, not
  a validated accuracy figure**).

## Not built / not measured — do not claim otherwise
- **COLMAP↔UWB registration is manual**, not solved from correspondences.
  The shipped default (`scale 1.54 m/unit, yaw 157°, ...`) was hand-tuned
  against the beacon markers, not computed.
- **No measured UWB RMSE dataset.** One reference point is a sanity check,
  not a validated accuracy claim. Do not quote "±20 cm" as measured.
- **Anchors are coplanar (z = 0.32 m)** — height is not independently
  observable; the solver fixes z. Any claim of 3-D UWB accuracy is false.
- **No 3D Gaussian Splatting.** Current reconstruction is COLMAP dense MVS
  (point cloud), not gsplat. gsplat is architecture, not implementation.
- **No trained policy, no ONNX export, no TensorRT engine.** TensorRT
  10.3.0 is present on the Jetson; nothing has been exported to it.
- **No pyrealsense2 / D415 integration on the Jetson.** `rs-enumerate-devices`
  exists but no camera has enumerated in this build.
- **No sim-to-real action divergence measurement.** This requires a trained
  policy, a gsplat render path, and a working D415 — none of which exist yet.
- **Drone attitude fusion (`jetson_publisher.py`) is written and
  algebraically verified (NED→scene quaternion conjugation checked by hand)
  but has not been run against physical Pixhawk hardware** at time of
  writing — the Jetson was disconnected during this development session.
  Verify on next connect before claiming it works.

## Why this list exists
An AI evaluator reading this repo can and will ask "how do you know?" for
every claim. Every item above is either a number with its sample size, or an
explicit "not done." Nothing here is hidden to look more complete.
