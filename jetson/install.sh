#!/usr/bin/env bash
# Bring the full SimRank UWB pipeline up on the Jetson, from a fresh clone.
#
# Idempotent: safe to re-run after reconnecting hardware, pulling new code,
# or rebooting. Installs/updates four chained systemd services:
#
#   uwb-listener     tag serial (ttyACM, by-id) -> uwb_ranging.jsonl
#   uwb-trilaterate  jsonl -> live (x,y) solve  -> tag_position_state.json
#   uwb-dashboard    local Flask viewer on :8080 (no internet required)
#   uwb-publisher    state + Pixhawk attitude   -> hosted Vercel viewer
#
# Known simplification: data file paths in the jetson/*.py scripts are
# hardcoded to /home/anupamsoni (this rig's actual provisioned user), not
# parameterized. Fine for a single physical device; would need an env-var
# rework for a fleet.
#
# Usage:
#   git clone https://github.com/TheOnlyOne001/SimRack.git ~/simrank
#   cd ~/simrank/jetson && ./install.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JETSON_DIR="$REPO_DIR/jetson"
TARGET_USER="$(whoami)"
TARGET_HOME="$HOME"
ENDPOINT="${SIMRANK_ENDPOINT:-https://simrank-room-scan.vercel.app/api/position}"
UNIT_DIR="/etc/systemd/system"

echo "== SimRank Jetson install =="
echo "   repo:     $REPO_DIR"
echo "   user:     $TARGET_USER"
echo "   home:     $TARGET_HOME"
echo "   endpoint: $ENDPOINT"
echo

if [ ! -f "$JETSON_DIR/uwb_listener.py" ]; then
  echo "error: run this from a clone of the repo (jetson/uwb_listener.py not found)" >&2
  exit 1
fi

echo "-- checking python dependencies --"
MISSING=()
python3 -c "import scipy" 2>/dev/null || MISSING+=("scipy")
python3 -c "import numpy" 2>/dev/null || MISSING+=("numpy")
python3 -c "import flask" 2>/dev/null || MISSING+=("flask")
python3 -c "import pymavlink" 2>/dev/null || MISSING+=("pymavlink")
if [ "${#MISSING[@]}" -gt 0 ]; then
  echo "   installing: ${MISSING[*]}"
  pip3 install --user "${MISSING[@]}"
else
  echo "   all present (scipy, numpy, flask, pymavlink)"
fi

echo "-- anchor survey --"
if [ ! -f "$TARGET_HOME/anchor_positions.json" ]; then
  if [ -f "$REPO_DIR/anchors.json" ]; then
    echo "   no anchor_positions.json in \$HOME yet -- seeding from repo anchors.json"
    python3 -c "
import json
d = json.load(open('$REPO_DIR/anchors.json'))
json.dump(d['anchors'], open('$TARGET_HOME/anchor_positions.json', 'w'), indent=2)
"
  else
    echo "   WARNING: no anchor survey found anywhere -- trilaterate.py will not start" >&2
  fi
else
  echo "   found existing $TARGET_HOME/anchor_positions.json, leaving it as-is"
fi

echo "-- installing systemd units --"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
for unit in uwb-listener uwb-trilaterate uwb-dashboard uwb-publisher; do
  sed -e "s#__USER__#$TARGET_USER#g" \
      -e "s#__HOME__#$TARGET_HOME#g" \
      -e "s#__ENDPOINT__#$ENDPOINT#g" \
      "$JETSON_DIR/systemd/$unit.service" > "$TMP/$unit.service"
  sudo cp "$TMP/$unit.service" "$UNIT_DIR/$unit.service"
  echo "   installed $unit.service"
done

echo "-- reloading and starting services --"
sudo systemctl daemon-reload
sudo systemctl enable --now uwb-listener.service
sleep 1
sudo systemctl enable --now uwb-trilaterate.service
sleep 1
sudo systemctl enable --now uwb-dashboard.service
sudo systemctl enable --now uwb-publisher.service

echo
echo "== status =="
systemctl status uwb-listener uwb-trilaterate uwb-dashboard uwb-publisher \
  --no-pager -l | grep -E "●|Active:"

echo
echo "Local dashboard : http://$(hostname -I 2>/dev/null | awk '{print $1}'):8080/"
echo "Hosted viewer   : https://simrank-room-scan.vercel.app/  (live once uwb-publisher is running)"
echo "Logs            : journalctl -u uwb-publisher -f"
