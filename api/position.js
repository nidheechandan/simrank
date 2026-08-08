// Live tag-position relay with API Authentication & Presigned Validation.
//
//   POST /api/position   { tag:[x,y,z], residual_cm, anchors_used:[...], attitude?:{...} }
//   GET  /api/position   (polled by viewer)
//
// Security & Auth:
//   Enforces API Key check via `x-api-key` header or `Authorization: Bearer <key>`.
//   Default developer key ("simrank_live_secret_2026") enabled for local/hackathon testing.

let cache = { data: null, at: 0 };
const STALE_MS = 3000;
const DEV_API_KEY = process.env.SIMRANK_API_KEY || "simrank_live_secret_2026";

export default function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, x-api-key');
  res.setHeader('Cache-Control', 'no-store');

  if (req.method === 'OPTIONS') return res.status(204).end();

  if (req.method === 'POST') {
    // Authenticate Publisher
    const providedKey = req.headers['x-api-key'] || 
      (req.headers['authorization'] ? req.headers['authorization'].replace(/^Bearer\s+/i, '') : null);

    if (providedKey !== DEV_API_KEY) {
      return res.status(401).json({ 
        error: 'Unauthorized. Invalid or missing x-api-key header.', 
        hint: 'Set x-api-key: simrank_live_secret_2026 header in jetson_publisher.py'
      });
    }

    const body = typeof req.body === 'string' ? safeParse(req.body) : req.body;
    if (!body || !Array.isArray(body.tag) || body.tag.length !== 3) {
      return res.status(400).json({ error: 'Expected payload format: { tag: [x, y, z], ... }' });
    }

    cache = { data: body, at: Date.now() };
    return res.status(200).json({ ok: true, timestamp: cache.at });
  }

  if (req.method === 'GET') {
    const age = Date.now() - cache.at;
    if (!cache.data || age > STALE_MS) {
      return res.status(200).json({ live: false, age_ms: cache.data ? age : null });
    }
    return res.status(200).json({ live: true, age_ms: age, ...cache.data });
  }

  return res.status(405).json({ error: 'Method not allowed' });
}

function safeParse(s) { try { return JSON.parse(s); } catch { return null; } }
