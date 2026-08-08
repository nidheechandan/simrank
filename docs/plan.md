# SimRank — Final Plan

**A motion-capture-free harness for measuring whether a simulator can predict real-hardware policy behaviour.**

Neurobots Championship 2026 · IES College of Engineering, Thrissur
Hardware: Jetson Orin Nano 8GB · Intel RealSense D415 · Qorvo DWM3001CDK UWB · payload drone (assembled on site, Holybro H-Flow) · rented Lambda GPU

---

## 1. The claim

> We reconstruct a real space as a metric-accurate simulated world, train flight policies in it, and show that **policy performance measured in simulation predicts policy behaviour on real hardware** — using ~₹20,000 of UWB radios in place of a ₹50 lakh motion-capture volume.

One sentence, falsifiable, with a number attached to every part. That is the whole pitch.

We are reproducing the central result of World Labs' R2S2R engine (published 28 July 2026) — that aligned simulation preserves policy ranking — at hackathon scale, on commodity hardware, with open tooling.

**What we are not claiming:** we have not built a generative world model, we have not achieved autonomous flight, and we are not claiming absolute success-rate parity between sim and reality.

---

## 2. Why this design, given our two hard constraints

### Constraint A — no flying permission

This removes a demo, not the result. And it forces a better experiment.

A "success rate over 10 real flights" was always weak evidence: n=10 is noise. What actually determines transfer is whether a policy **produces the same action given real sensor input as it does given simulated sensor input at the same pose.** That is measurable without leaving the ground, and it yields thousands of paired samples instead of ten.

So we measure the sim-to-real gap directly, at the policy's input/output interface. See §4.

### Constraint B — the evaluator is an AI agent

This inverts the usual hackathon strategy. A live 3D dashboard cannot impress an agent that reads text. What scores well instead:

| Deprioritise | Prioritise |
|---|---|
| Visual spectacle | Precise, falsifiable claims |
| Rehearsed demo theatre | A clean, readable repo |
| Persuasive framing | Numbers with sample sizes and conditions |
| Hiding weaknesses | Surfacing limitations first |

An LLM interviewer probes with *"how do you know?"*, *"what's your baseline?"*, *"what would falsify this?"* and — critically — **catches contradictions across a conversation** far more reliably than a tired human judge at 4pm. Every team member must quote identical numbers. See §9.

**Action item:** find out the interview format (text? voice? does the agent read our repo?). Design assumes it can read submitted artifacts. Confirm this.

---

## 3. Hardware roles

Every item has one load-bearing job. Nothing is decorative.

| Item | Job | Why it and not something else |
|---|---|---|
| **Phone** | Capture 250–400 stills for reconstruction | D415's 65°×40° FOV and rolling shutter are wrong for room-scale capture; wide FOV covers the scene in fewer, sharper frames |
| **D415** | (1) Metric scale cross-check (2) depth supervision to kill floaters (3) the policy's live input at deploy | Photo reconstruction is scale-ambiguous; a wrongly-scaled sim looks perfect and teaches wrong distances |
| **Jetson Orin Nano** | Runs the policy on live D415 depth | Deployment target — proves the policy runs on real edge hardware, not a laptop |
| **UWB (4–6 anchors)** | Ground-truth pose logging | The motion-capture replacement — this *is* the pitch |
| **Drone + H-Flow** | Physical platform; H-Flow altitude if integration lands in time | Deliberately **not on the critical path** — see §8 |
| **Lambda GPU** | Reconstruction + policy training | Nothing heavy runs on the Jetson |

**The single most important implementation detail:** the simulator's camera must render at the **D415's exact intrinsics** — 65°×40°, matching resolution, pulled from the SDK into one JSON file that both the sim config and the Jetson code read. Train on a generic 90° camera and deploy on a 65° one and the policy sees a different world. One source of truth, no exceptions.

---

## 4. The experiment

### Protocol

1. **Build a physical course** in the venue — obstacles and gates, matte surfaces, controlled lighting.
2. **Scan it** with the phone. Include a 1.000 m reference bar in frame.
3. **Reconstruct** on Lambda: COLMAP poses → gsplat → mesh for collision. Scale by the reference bar; cross-check against D415 metric depth. Two independent estimates agreeing means we can trust the sim is in metres.
4. **Traverse** the course ~10 times carrying the rig (drone powered, props off, on a handle). UWB logs true pose. D415 records real depth. The policy runs live on the Jetson, logging its commanded action every frame.
5. **Replay** those exact logged poses through the sim. Render depth from the reconstruction at D415 intrinsics. Run the **same policy** on the **same poses**. Log sim-side actions.
6. Result: thousands of paired (real-input action, sim-input action) samples at matched poses.

### Metrics

| Metric | Definition | What it establishes |
|---|---|---|
| **Action divergence** | Mean absolute + cosine distance between real-input and sim-input actions at matched poses | The sim-to-real gap, measured directly |
| **Depth domain gap** | Distributional distance between rendered and real depth at matched poses | Where the reconstruction is unfaithful |
| **Sim success rate** | Closed-loop success over ~500 sim rollouts per policy | Cheap, high-n policy scoring |
| **Rank correlation** | Spearman ρ between sim success rate and (inverse) action divergence, across 4 policies | **The headline result** |

### The three ablations

These are what elevate this from an integration project to a result. Each one proves a design decision was load-bearing.

| Ablation | Prediction | Proves |
|---|---|---|
| Sim scaled to 0.85× | Action divergence spikes | Metric scale is essential — the D415's job is real |
| Sim rendered at 90° instead of 65° | Action divergence spikes | Intrinsics matching is essential |
| Depth-noise randomisation disabled | Divergence increases on real input | Domain randomisation is doing work |

Run these. They cost almost nothing (re-render, re-evaluate) and they are the best possible answer to *"how do you know your design choices mattered?"*

---

## 5. Stack

| Stage | Tool | Rationale |
|---|---|---|
| Poses | COLMAP | Standard; everything downstream expects it |
| Splat | gsplat | ~4× less training memory, up to 15% faster than reference 3DGS, negligible quality difference |
| Fallback | Nerfstudio splatfacto | `pip install`, one command, shares the gsplat backend |
| Sim | GaussGym → Aerial Gym → MuJoCo Playground | Descending ambition; pick the highest that stands up in testing |
| Deploy | ONNX → TensorRT | Only inference runs on the Orin |
| Logging | Rerun | Secondary given an AI evaluator, but produces the plots for the repo |

---

## 6. Pre-event build — gates

Nothing proceeds until the previous gate is genuinely true. Event day should be re-running a pipeline already run twice.

**Gate 1 — tonight, four people in parallel**
- librealsense streams 30 min continuous on the Jetson, no dropouts (use Intel's own cable)
- A dummy ONNX model with random weights runs in TensorRT, output numerically verified against PyTorch
- Lambda instance renders one headless frame (EGL / virtual display configured)
- COLMAP + gsplat installed and reconstructs a test scene

**Gate 2 — full chain on a room at home, twice**
Phone photos → COLMAP → gsplat → scale → mesh → sim scene → 10 min training → ONNX export. **Record the wall-clock time of every stage.** Those timings are the 24-hour budget.

**Gate 3 — policy runs on the Jetson from live D415 input**, emitting sane velocity commands. Measure end-to-end latency; feed it back into sim as an action delay.

**Gate 4 — UWB rig measures a hand-carried path to under 20 cm.** Anchors at **two different heights** — coplanar anchors blow z-error out to roughly a metre. Hand-survey anchor positions with a tape or laser; do not trust the built-in autopositioning.

**Gate 5 — four policies pre-trained** on varied scenes, deliberately spanning a quality range. If they all score alike, the ranking has no spread and the correlation is meaningless.

---

## 7. The 24 hours

Training is the slow half; evaluation is the fast half. **We do not train on site.** We arrive with policies and evaluate them against the venue.

| Hours | Activity |
|---|---|
| 0–2 | Assemble drone, mount rig, deploy and survey UWB anchors, build the course |
| 2–3 | Phone scan of the course + D415 clip + reference bar |
| 3–5 | Reconstruct on Lambda: poses → splat → scale → mesh → sim scene |
| 5–7 | Sim evaluation: ~500 rollouts × 4 policies, produce sim ranking |
| 7–9 | Real traversals: 10 runs, logging UWB pose + D415 depth + live policy actions |
| 9–12 | Pose-matched replay through sim; compute action divergence |
| 12–15 | Three ablations |
| 15–18 | Plots, results table, README, repo cleanup |
| 18–21 | Write the results document and the limitations section |
| 21–24 | Rehearse Q&A; whole team memorises the facts sheet |

---

## 8. De-risking

**The drone is deliberately off the critical path.** It is bought and assembled on site and therefore untested. Since we are not flying, it contributes a physical platform and — if integration lands in time — H-Flow altitude. If the flight controller does not come up, **the UWB rig alone carries pose**, provided anchors are at two heights. Nothing else depends on the airframe.

| Risk | Mitigation |
|---|---|
| Venue WiFi + Lambda + deadline = three serial failure points | Reserve and validate the instance beforehand; keep a laptop-GPU degraded path; if possible scan the venue in advance and arrive with the sim already built |
| GaussGym rides deprecated IsaacGym Preview (pinned CUDA/Python, headless rendering) | Solve at Gate 1; Aerial Gym and MuJoCo Playground standing by |
| TensorRT FP16 silently producing wrong values | Numerical verification at Gate 1 and again on site |
| Reconstruction fails on venue surfaces | Matte props, controlled lighting, locked phone exposure; fallback to a pre-scanned room |
| Scale estimate wrong | Two independent estimates (reference bar + D415) must agree before proceeding |

**Locked phone exposure** deserves its own line: varying ISO/shutter between frames is the most common cause of a ruined capture and takes five seconds to prevent.

---

## 9. Deliverables for the AI evaluator

### Repo structure
```
README.md              # claim, method, results table, repro commands
results/
  headline.md          # the rank correlation, with n and conditions
  ablations.md         # three ablations, each with prediction vs outcome
  plots/               # sim vs real divergence, per-policy
  raw/                 # UWB logs, action logs, depth stats
LIMITATIONS.md         # written before we know the results
pipeline/              # scan → reconstruct → train → deploy, each runnable
```

### The facts sheet
One page. Every team member memorises it. An AI interviewer will catch inconsistency between members instantly.

- Number of policies evaluated, and their sim success rates
- Sim rollouts per policy; real traversals; matched pose pairs
- Rank correlation with its p-value
- UWB measured accuracy (our own number, not the datasheet's)
- Scale factor and the agreement between the two estimates
- Each ablation's numbers

### Writing rules
- Every claim carries a number, a sample size, and a condition
- No "revolutionary", "first ever", "state of the art"
- Limitations section written **before** results are known, so it isn't retrofitted
- Raw logs and plots included, not just conclusions

---

## 10. Anticipated questions

**"How do you know your simulator is accurate?"**
We don't claim it is. We claim it's *predictive*, which is a weaker and testable claim: policies ranking better in sim show lower action divergence on real hardware. Rank correlation ρ = [X] over 4 policies. Absolute fidelity is not required for the simulator to support the same decisions as reality.

**"Four policies is a small sample."**
Correct, and it is our main limitation. With n=4 a preserved ranking could be chance. We report it as suggestive, not conclusive, and we strengthen it with thousands of matched-pose samples per policy rather than relying on the ranking alone.

**"You didn't fly. Does this mean anything?"**
Flight would have given ~10 noisy trials. Pose-matched replay gives thousands of paired samples at the interface that actually determines transfer. It is more data and a more direct measurement, not a substitute for a demo we couldn't run.

**"Isn't this just Isaac Sim?"**
Isaac Sim is the better simulator and the wrong tool here. Omniverse expects authored USD assets with tuned materials; our input is a messy scan. Splat rendering needs no material authoring — the appearance *is* the photographs — and rasterisation is fast enough for visual RL where ray tracing isn't. Omniverse gives you *a* photorealistic world; this gives you *this* world.

**"What would falsify your claim?"**
If sim ranking and real-input divergence ranking were uncorrelated or inversely correlated. We would report that; the ablations are designed so a null result still tells us which component broke.

**"What did you actually build versus integrate?"**
Integrated: COLMAP, gsplat, the simulator, TensorRT. Built: the UWB ground-truth rig and calibration, the pose-matched replay harness, the scale-resolution procedure, the deployment path, and the three ablations. The replay harness and the ablations are the contribution.

---

## 11. Limitations

Stated plainly, and first.

- **n=4 policies.** A preserved ranking at this sample size could be chance.
- **No flight.** We measure open-loop action agreement at matched poses, not closed-loop flight success. Closed-loop dynamics could diverge in ways this does not capture.
- **One environment.** Everything is measured in a single reconstructed room. Generalisation across environments is untested.
- **UWB accuracy is our own measurement**, not an independently validated figure, and the DWM3001CDK has no peer-reviewed drone-vs-motion-capture validation we are aware of.
- **The D415 is used outside its ideal envelope** in places — it degrades past ~3 m and on glossy or dark surfaces, which bounds course design.
- **We reproduce a principle, not an engine.** World Labs' system is proprietary, manipulation-focused, and vastly more capable. We test its evaluation-prediction principle on a drone with open tools.

---

## 12. In plain terms

We photograph a room and turn it into a video-game version of that room, accurate to the centimetre. We let several drone brains practise flying in it. We rank them by how well they do.

Then we carry the real drone through the real room and check whether each brain reacts the same way to what the real camera sees as it did to what the simulated camera showed it.

If the video game picked the same winner, we've shown something useful: teams can stop crashing real drones to find out which software is better.

Proving that normally needs a ₹50 lakh motion-capture room. We used a handful of cheap radios taped to the walls.
