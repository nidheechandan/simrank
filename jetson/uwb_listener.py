#!/usr/bin/env python3
"""Continuous UWB ranging listener for the DWM3001CDK tag on /dev/ttyACM0.

Reads SESSION_INFO_NTF blocks from the tag's CLI console, parses them into
structured JSON records (one per ranging block), appends them to a log file,
and prints them to stdout for live monitoring via journalctl.
"""
import serial
import time
import re
import json
import sys
from datetime import datetime, timezone

PORT = "/dev/ttyACM0"
BAUD = 115200
LOG_PATH = "/home/anupamsoni/uwb_ranging.jsonl"

HEADER_RE = re.compile(
    r'SESSION_INFO_NTF:\s*\{session_handle=(\d+),\s*sequence_number=(\d+),\s*block_index=(\d+),\s*n_measurements=(\d+)'
)
MEAS_RE = re.compile(
    r'mac_address=0x([0-9a-fA-F]+),\s*status="([A-Z_]+)"(?:,\s*distance\[cm\]=(-?\d+))?'
)


def open_serial():
    while True:
        try:
            return serial.Serial(PORT, BAUD, timeout=1)
        except (serial.SerialException, FileNotFoundError):
            print(f"[{datetime.now(timezone.utc).isoformat()}] waiting for {PORT}...", file=sys.stderr, flush=True)
            time.sleep(2)


def parse_block(block_text):
    hdr = HEADER_RE.search(block_text)
    if not hdr:
        return None
    session_handle, seq, block_index, n = hdr.groups()
    measurements = {}
    for m in MEAS_RE.finditer(block_text):
        addr = int(m.group(1), 16)
        status = m.group(2)
        dist = int(m.group(3)) if m.group(3) is not None else None
        measurements[addr] = {"status": status, "distance_cm": dist}
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_handle": int(session_handle),
        "sequence_number": int(seq),
        "block_index": int(block_index),
        "n_measurements": int(n),
        "measurements": measurements,
    }


def main():
    ser = open_serial()
    print(f"listening on {PORT} @ {BAUD}", flush=True)
    block_lines = []
    collecting = False
    with open(LOG_PATH, "a", buffering=1) as logf:
        while True:
            try:
                raw = ser.readline()
            except (serial.SerialException, OSError):
                print("serial error, reconnecting...", file=sys.stderr, flush=True)
                try:
                    ser.close()
                except Exception:
                    pass
                ser = open_serial()
                continue
            if not raw:
                continue
            line = raw.decode(errors="replace").rstrip("\r\n")
            if "SESSION_INFO_NTF" in line:
                collecting = True
                block_lines = [line]
                if line.rstrip().endswith("}"):
                    collecting = False
                    record = parse_block("\n".join(block_lines))
                    if record:
                        logf.write(json.dumps(record) + "\n")
                        print(json.dumps(record), flush=True)
                continue
            if collecting:
                block_lines.append(line)
                if line.rstrip().endswith("}"):
                    collecting = False
                    record = parse_block("\n".join(block_lines))
                    if record:
                        logf.write(json.dumps(record) + "\n")
                        print(json.dumps(record), flush=True)


if __name__ == "__main__":
    main()
