// Live tag-position relay.
//
//   POST /api/position   { tag:[x,y,z], residual_cm, anchors_used:[...],
//                           attitude?:{roll,pitch,yaw,quat_xyzw,age_ms} }    <- pushed by the Jetson
//   GET  /api/position                                                      <- polled by the viewer
//
// `attitude` is optional and passed through unmodified (see the `...body` spread below) --
// jetson_publisher.py only includes it when the Pixhawk MAVLink link is live, so this relay
// works identically whether or not the flight controller is connected.
//
// NOTE ON STATE: Vercel functions are stateless and may run on many instances, so this
// module-scope cache only survives within a warm instance. It is adequate for a single-room
// live demo (one publisher, few viewers) and degrades to "offline" rather than lying.
// For durable state, swap `cache` for Vercel KV / Redis — the request contract stays identical.

let cache = { data: null, at: 0 };

const STALE_MS = 3000; // no push within this window => report offline

export default function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  res.setHeader('Cache-Control', 'no-store');

  if (req.method === 'OPTIONS') return res.status(204).end();

  if (req.method === 'POST') {
    const body = typeof req.body === 'string' ? safeParse(req.body) : req.body;
    if (!body || !Array.isArray(body.tag) || body.tag.length !== 3) {
      return res.status(400).json({ error: 'expected { tag:[x,y,z], ... }' });
    }
    cache = { data: body, at: Date.now() };
    return res.status(200).json({ ok: true });
  }

  if (req.method === 'GET') {
    const age = Date.now() - cache.at;
    if (!cache.data || age > STALE_MS) {
      return res.status(200).json({ live: false, age_ms: cache.data ? age : null });
    }
    return res.status(200).json({ live: true, age_ms: age, ...cache.data });
  }

  return res.status(405).json({ error: 'method not allowed' });
}

function safeParse(s) { try { return JSON.parse(s); } catch { return null; } }
