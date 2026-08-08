#!/usr/bin/env python3
"""Live UWB position dashboard. Serves /position (JSON) and / (Plotly 3D view)."""
import json
import os
from flask import Flask, jsonify, Response

STATE_PATH = "/home/anupamsoni/tag_position_state.json"

app = Flask(__name__)

PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>UWB Ground-Truth Live Position</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>
  html,body { margin:0; height:100%; background:#0b0f14; color:#e6edf3; font-family: -apple-system, Segoe UI, Roboto, sans-serif; }
  #plot { width:100vw; height:82vh; }
  #stats { padding: 10px 20px; font-size: 15px; display:flex; gap:28px; flex-wrap:wrap; }
  .stat b { color:#5ec2ff; }
  #title { padding: 10px 20px 0 20px; font-size: 18px; font-weight:600; }
</style>
</head>
<body>
<div id="title">UWB Ground-Truth Rig &mdash; Live Multilateration (7 anchors)</div>
<div id="plot"></div>
<div id="stats">
  <div class="stat">Anchors locked: <b id="n_anchors">-</b></div>
  <div class="stat">Fit residual: <b id="resid">-</b> cm</div>
  <div class="stat">Tag position (m): <b id="pos">-</b></div>
  <div class="stat">Block: <b id="block">-</b></div>
  <div class="stat">Status: <b id="status">connecting...</b></div>
</div>
<script>
let trail = [];
const MAX_TRAIL = 200;
let anchorsPlotted = false;

function initPlot(anchors) {
  const axIds = Object.keys(anchors);
  const ax = axIds.map(k => anchors[k][0]);
  const ay = axIds.map(k => anchors[k][1]);
  const az = axIds.map(k => anchors[k][2]);

  const anchorTrace = {
    x: ax, y: ay, z: az, mode: 'markers+text',
    type: 'scatter3d',
    text: axIds.map(k => 'A' + k),
    textposition: 'top center',
    marker: { size: 6, color: '#ff7043', symbol: 'diamond' },
    name: 'anchors'
  };
  const tagTrace = {
    x: [], y: [], z: [], mode: 'markers',
    type: 'scatter3d',
    marker: { size: 9, color: '#5ec2ff' },
    name: 'tag'
  };
  const trailTrace = {
    x: [], y: [], z: [], mode: 'lines',
    type: 'scatter3d',
    line: { color: '#5ec2ff', width: 3 },
    opacity: 0.5,
    name: 'trail'
  };

  const layout = {
    paper_bgcolor: '#0b0f14', plot_bgcolor: '#0b0f14',
    font: { color: '#e6edf3' },
    scene: {
      xaxis: { title: 'x (m)', gridcolor: '#233', backgroundcolor: '#0b0f14' },
      yaxis: { title: 'y (m)', gridcolor: '#233', backgroundcolor: '#0b0f14' },
      zaxis: { title: 'z (m)', gridcolor: '#233', backgroundcolor: '#0b0f14' },
      aspectmode: 'data'
    },
    margin: { l: 0, r: 0, t: 0, b: 0 },
    showlegend: true,
    legend: { font: { color: '#e6edf3' } }
  };

  Plotly.newPlot('plot', [anchorTrace, trailTrace, tagTrace], layout, {responsive: true});
  anchorsPlotted = true;
}

async function poll() {
  try {
    const r = await fetch('/position');
    if (!r.ok) { document.getElementById('status').textContent = 'no data yet'; return; }
    const d = await r.json();

    if (!anchorsPlotted) initPlot(d.anchors);

    trail.push(d.tag);
    if (trail.length > MAX_TRAIL) trail.shift();

    Plotly.restyle('plot', {
      x: [trail.map(p => p[0])], y: [trail.map(p => p[1])], z: [trail.map(p => p[2])]
    }, [1]);
    Plotly.restyle('plot', {
      x: [[d.tag[0]]], y: [[d.tag[1]]], z: [[d.tag[2]]]
    }, [2]);

    document.getElementById('n_anchors').textContent = d.anchors_used.length;
    document.getElementById('resid').textContent = d.residual_cm.toFixed(1);
    document.getElementById('pos').textContent = d.tag.map(v => v.toFixed(2)).join(', ');
    document.getElementById('block').textContent = d.block_index;
    document.getElementById('status').textContent = 'live';
  } catch (e) {
    document.getElementById('status').textContent = 'connection error';
  }
}

setInterval(poll, 150);
poll();
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return Response(PAGE, mimetype="text/html")


@app.route("/position")
def position():
    if not os.path.exists(STATE_PATH):
        return jsonify({"error": "no data yet"}), 503
    with open(STATE_PATH) as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return jsonify({"error": "state file busy"}), 503
    return jsonify(data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, threaded=True)
