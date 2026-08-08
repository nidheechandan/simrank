#!/usr/bin/env python3
"""Publish live UWB position + Pixhawk attitude to the hosted SimRank viewer.

Two independent, gracefully-degrading data sources are fused at publish time:

  1. UWB position   <- tag_position_state.json, written by trilaterate.py
                        (~5 Hz, matches the FiRa 200 ms block rate)
  2. Pixhawk attitude <- MAVLink ATTITUDE messages, read in a background thread
                        (~10-50 Hz depending on autopilot stream rate config)

If the Pixhawk is not connected, this still publishes UWB-only position (no
"attitude" key) -- the viewer already renders that as an unoriented marker, so
startup does not depend on both devices being present. If UWB has no fresh
frame, nothing is published and the API's own staleness timeout marks the
scene "offline" rather than showing a stuck marker.

Usage:
    python3 jetson_publisher.py [--endpoint URL] [--mavlink PORT] [--no-mavlink]

Designed to run as the uwb-publisher systemd unit (see jetson/install.sh),
chained after uwb-trilaterate.service so it starts once real position data
exists.
"""
import argparse
import json
import math
import os
import sys
import threading
import time
import urllib.request

STATE_PATH = "/home/anupamsoni/tag_position_state.json"
DEFAULT_ENDPOINT = "https://simrank-room-scan.vercel.app/api/position"
# Stable udev path, not /dev/ttyACM0 -- device numbering depends on plug order
# (see: the Pixhawk grabbed ttyACM0 out from under the UWB tag earlier in this
# build, which is exactly the bug a by-id path avoids).
DEFAULT_MAVLINK = "/dev/serial/by-id/usb-ArduPilot_Pixhawk1_20001F001451333532363834-if00"
PUBLISH_PERIOD_S = 0.2  # matches the ~5 Hz UWB block rate; attitude is just sampled at publish time


class AttitudeReader:
    """Background MAVLink listener. Exposes the most recent (roll, pitch, yaw, age)."""

    def __init__(self, port, baud=115200):
        self.port = port
        self.baud = baud
        self._lock = threading.Lock()
        self._roll = self._pitch = self._yaw = None
        self._ts = 0.0
        self._connected = False
        self._stop = False

    def start(self):
        t = threading.Thread(target=self._run, daemon=True)
        t.start()
        return self

    def _run(self):
        try:
            from pymavlink import mavutil
        except ImportError:
            print("pymavlink not installed -- attitude publishing disabled", file=sys.stderr)
            return

        while not self._stop:
            try:
                print(f"[attitude] connecting to {self.port} @ {self.baud}", flush=True)
                conn = mavutil.mavlink_connection(self.port, baud=self.baud)
                conn.wait_heartbeat(timeout=10)
                self._connected = True
                print(f"[attitude] heartbeat from system {conn.target_system} "
                      f"component {conn.target_component}", flush=True)

                # Ask for ATTITUDE at a decent rate; some firmwares stream it by
                # default, this just makes sure.
                conn.mav.request_data_stream_send(
                    conn.target_system, conn.target_component,
                    mavutil.mavlink.MAV_DATA_STREAM_EXTRA1, 10, 1)

                while not self._stop:
                    msg = conn.recv_match(type="ATTITUDE", blocking=True, timeout=5)
                    if msg is None:
                        continue
                    with self._lock:
                        self._roll, self._pitch, self._yaw = msg.roll, msg.pitch, msg.yaw
                        self._ts = time.time()
            except Exception as e:
                self._connected = False
                print(f"[attitude] connection lost/failed: {e} -- retrying in 3s", file=sys.stderr)
                time.sleep(3)

    def latest(self, max_age_s=1.0):
        """Returns dict with roll/pitch/yaw/quat, or None if stale/unavailable."""
        with self._lock:
            roll, pitch, yaw, ts = self._roll, self._pitch, self._yaw, self._ts
        if roll is None or (time.time() - ts) > max_age_s:
            return None
        qx, qy, qz, qw = euler_to_quat(roll, pitch, yaw)
        return {
            "roll": roll, "pitch": pitch, "yaw": yaw,
            "quat_xyzw": [qx, qy, qz, qw],
            "age_ms": round((time.time() - ts) * 1000, 1),
        }


def euler_to_quat(roll, pitch, yaw):
    """Standard aerospace ZYX intrinsic Euler (roll about X, pitch about Y, yaw
    about Z, applied yaw-then-pitch-then-roll) -> quaternion (x, y, z, w).
    This matches the MAVLink ATTITUDE message convention (NED, radians)."""
    cr, sr = math.cos(roll * 0.5), math.sin(roll * 0.5)
    cp, sp = math.cos(pitch * 0.5), math.sin(pitch * 0.5)
    cy, sy = math.cos(yaw * 0.5), math.sin(yaw * 0.5)
    qw = cr * cp * cy + sr * sp * sy
    qx = sr * cp * cy - cr * sp * sy
    qy = cr * sp * cy + sr * cp * sy
    qz = cr * cp * sy - sr * sp * cy
    return qx, qy, qz, qw


DEFAULT_API_KEY = os.environ.get("SIMRANK_API_KEY", "simrank_live_secret_2026")


def post(endpoint, payload, api_key=DEFAULT_API_KEY):
    body = json.dumps(payload).encode()
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key
    }
    req = urllib.request.Request(
        endpoint, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=2) as r:
        return r.status


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    ap.add_argument("--mavlink", default=DEFAULT_MAVLINK)
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--no-mavlink", action="store_true",
                     help="publish UWB position only, skip Pixhawk entirely")
    args = ap.parse_args()

    attitude = None
    if not args.no_mavlink:
        attitude = AttitudeReader(args.mavlink, args.baud).start()

    print(f"publishing {STATE_PATH} -> {args.endpoint} @ {1/PUBLISH_PERIOD_S:.0f} Hz "
          f"(attitude: {'disabled' if args.no_mavlink else args.mavlink})", flush=True)

    last_block = None
    sent = 0
    while True:
        time.sleep(PUBLISH_PERIOD_S)
        try:
            with open(STATE_PATH) as f:
                st = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue

        if st.get("block_index") == last_block:
            continue
        last_block = st.get("block_index")

        payload = {
            "tag": st["tag"],
            "residual_cm": st.get("residual_cm"),
            "anchors_used": st.get("anchors_used", []),
            "block_index": st.get("block_index"),
            "t": st.get("t"),
        }
        att = attitude.latest() if attitude else None
        if att:
            payload["attitude"] = att

        try:
            post(args.endpoint, payload)
            sent += 1
            if sent % 50 == 0:
                tag = payload["tag"]
                att_str = f", yaw={math.degrees(att['yaw']):.0f}deg" if att else " (no attitude)"
                print(f"  {sent} frames published (tag={tag}{att_str})", flush=True)
        except Exception as e:
            print(f"  publish failed: {e}", flush=True)
            time.sleep(1)


if __name__ == "__main__":
    main()
