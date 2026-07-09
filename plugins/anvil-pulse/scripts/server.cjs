#!/usr/bin/env node
/**
 * anvil-pulse server — local operator dashboard for long autonomous anvil runs.
 *
 * Dependency-free (Node stdlib only). Reads anvil state two ways:
 *   1. `anvil status --json --cwd <project>`  — task rollups + per-claim
 *      phase / elapsed_seconds / lease_expires_in_seconds (retro-opps T012).
 *   2. Tail of the append-only events.jsonl — progress.noted / claim lifecycle
 *      stream (the workflow heartbeat bus).
 *
 * It never writes anvil state: status is a read verb and the JSONL is opened
 * read-only. Safe next to a live run (state.db is WAL; we don't even open it).
 *
 * Environment:
 *   PULSE_DIR            state dir for pid/log files (required by start-server.sh)
 *   PULSE_PROJECT_DIR    anvil project to watch (default: cwd)
 *   PULSE_HOST           bind host (default 127.0.0.1)
 *   PULSE_URL_HOST       hostname to show in the printed URL (default localhost)
 *   PULSE_PORT           fixed port (default: random high port)
 *   PULSE_ANVIL_BIN      anvil executable (default "anvil")
 *   PULSE_STATE_DIR      explicit anvil state dir containing events.jsonl
 *                        (default: auto-discover, see resolveEventsPath)
 *   PULSE_QUIET_SECONDS  no-activity threshold for "quiet" (default 300)
 *   PULSE_WEDGED_SECONDS no-activity threshold for "possibly-wedged" (default 900)
 *   PULSE_STATUS_TTL_MS  status subprocess cache TTL (default 2000)
 *   PULSE_OWNER_PID      exit when this pid dies (only if PULSE_WATCH_OWNER=1)
 */
'use strict';

const http = require('http');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFile, exec } = require('child_process');

const PROJECT_DIR = process.env.PULSE_PROJECT_DIR || process.cwd();
const BIND_HOST = process.env.PULSE_HOST || '127.0.0.1';
const URL_HOST = process.env.PULSE_URL_HOST || 'localhost';
const ANVIL_BIN = process.env.PULSE_ANVIL_BIN || 'anvil';
const QUIET_SECONDS = Number(process.env.PULSE_QUIET_SECONDS || 300);
const WEDGED_SECONDS = Number(process.env.PULSE_WEDGED_SECONDS || 900);
const STATUS_TTL_MS = Number(process.env.PULSE_STATUS_TTL_MS || 2000);
const EVENT_TAIL_BYTES = 256 * 1024; // read at most this much from the end
const EVENT_LIMIT = 80; // newest events returned to the page

// ---------------------------------------------------------------------------
// anvil status (cached subprocess)
// ---------------------------------------------------------------------------

let statusCache = { at: 0, promise: null };

// Conservative allowlist for the win32 shell fallback below. ANVIL_BIN and
// PROJECT_DIR are operator-supplied at process start (never from HTTP), but
// refusing metacharacters outright is simpler to trust than quoting them.
const SAFE_SHELL_ARG = /^[A-Za-z0-9_ .:\\/=-]+$/;

function execAnvil(args, opts, callback) {
  // On Windows the anvil CLI is typically a .cmd/.exe shim (uv/pipx) or a
  // shebang script under Git Bash; execFile resolves neither, so retry
  // through the shell — but only when every part is metacharacter-free.
  const shellFallback = () => {
    const parts = [ANVIL_BIN, ...args];
    if (parts.every((a) => SAFE_SHELL_ARG.test(a))) {
      exec(parts.map((a) => (/\s/.test(a) ? `"${a}"` : a)).join(' '), opts, callback);
      return;
    }
    callback(
      new Error(
        'anvil is not directly executable and its path contains shell metacharacters; set PULSE_ANVIL_BIN to the .exe'
      ),
      ''
    );
  };
  // ENOENT: shebang script / unresolvable name. EINVAL: Node's
  // CVE-2024-27980 hardening refuses to spawn .cmd/.bat without a shell —
  // and throws it SYNCHRONOUSLY from spawn, hence the try/catch.
  const isFallbackCode = (code) =>
    process.platform === 'win32' && (code === 'ENOENT' || code === 'EINVAL');
  try {
    execFile(ANVIL_BIN, args, opts, (err, stdout) => {
      if (err && isFallbackCode(err.code)) {
        shellFallback();
        return;
      }
      callback(err, stdout);
    });
  } catch (e) {
    if (isFallbackCode(e.code)) {
      shellFallback();
      return;
    }
    throw e;
  }
}

function fetchStatus() {
  const now = Date.now();
  if (statusCache.promise && now - statusCache.at < STATUS_TTL_MS) {
    return statusCache.promise;
  }
  statusCache.at = now;
  statusCache.promise = new Promise((resolve) => {
    const args = ['status', '--json', '--cwd', PROJECT_DIR];
    const opts = { timeout: 15000, windowsHide: true, maxBuffer: 4 * 1024 * 1024 };
    const callback = (err, stdout) => {
      // anvil exits 1 with an {ok:false} envelope for uninitialized projects;
      // both shapes parse — only report exec/parse failures as errors.
      try {
        resolve({ parsed: JSON.parse(String(stdout || '')), error: null });
      } catch (_) {
        resolve({
          parsed: null,
          error: err
            ? `anvil status failed: ${err.code || err.message}`
            : 'anvil status returned unparseable output',
        });
      }
    };
    execAnvil(args, opts, callback);
  });
  return statusCache.promise;
}

// ---------------------------------------------------------------------------
// events.jsonl discovery + tail
// ---------------------------------------------------------------------------

function resolveEventsPath() {
  if (process.env.PULSE_STATE_DIR) {
    return path.join(process.env.PULSE_STATE_DIR, 'events.jsonl');
  }
  // In-repo state dirs are opt-in; check them first because they are exact.
  const local = [
    path.join(PROJECT_DIR, '.anvil', 'events.jsonl'),
    path.join(PROJECT_DIR, 'bin', '.anvil', 'events.jsonl'),
  ];
  for (const p of local) {
    if (fs.existsSync(p)) return p;
  }
  // HOME workspace mode: ~/.anvil/workspaces/<key>/events.jsonl. The key is an
  // internal hash, so fall back to the most recently modified workspace log.
  // This is a heuristic — surface it as a warning in the payload.
  const wsRoot = path.join(os.homedir(), '.anvil', 'workspaces');
  try {
    let best = null;
    for (const entry of fs.readdirSync(wsRoot)) {
      const candidate = path.join(wsRoot, entry, 'events.jsonl');
      try {
        const st = fs.statSync(candidate);
        if (!best || st.mtimeMs > best.mtimeMs) {
          best = { path: candidate, mtimeMs: st.mtimeMs };
        }
      } catch (_) {
        /* not a workspace with events */
      }
    }
    if (best) return best.path;
  } catch (_) {
    /* no workspace root */
  }
  return null;
}

function tailEvents(eventsPath) {
  const out = { events: [], warning: null };
  if (!eventsPath) {
    out.warning =
      'events.jsonl not found (set PULSE_STATE_DIR to the anvil state dir); event feed disabled';
    return out;
  }
  let fd;
  try {
    fd = fs.openSync(eventsPath, 'r');
    const size = fs.fstatSync(fd).size;
    const start = Math.max(0, size - EVENT_TAIL_BYTES);
    const buf = Buffer.alloc(size - start);
    fs.readSync(fd, buf, 0, buf.length, start);
    const lines = buf.toString('utf8').split('\n');
    if (start > 0) lines.shift(); // first line may be a partial record
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      try {
        const ev = JSON.parse(trimmed);
        out.events.push({
          timestamp: ev.timestamp || null,
          action: ev.action || null,
          actor: ev.actor || null,
          target_id: ev.target_id || null,
          phase: (ev.payload && ev.payload.phase) || null,
          notes: (ev.payload && (ev.payload.detail || ev.payload.notes)) || null,
        });
      } catch (_) {
        /* skip malformed line */
      }
    }
  } catch (e) {
    out.warning = `could not read ${eventsPath}: ${e.code || e.message}`;
  } finally {
    if (fd !== undefined) fs.closeSync(fd);
  }
  out.events = out.events.slice(-EVENT_LIMIT).reverse(); // newest first
  return out;
}

// ---------------------------------------------------------------------------
// staleness classification (the folded-in stuck-detector)
// ---------------------------------------------------------------------------

function classifyClaim(claim, lastActivitySeconds) {
  if (
    typeof claim.lease_expires_in_seconds === 'number' &&
    claim.lease_expires_in_seconds <= 0
  ) {
    return 'lease-expired';
  }
  // With no event evidence at all, fall back to claim age: a young claim is
  // healthy (agent may not have produced tool output yet), an old silent one
  // is suspect.
  const age =
    lastActivitySeconds !== null ? lastActivitySeconds : claim.elapsed_seconds || 0;
  if (age < QUIET_SECONDS) return 'healthy';
  if (age < WEDGED_SECONDS) return 'quiet';
  return 'possibly-wedged';
}

function buildPulse(statusResult, eventsResult) {
  const warnings = [];
  if (statusResult.error) warnings.push(statusResult.error);
  if (eventsResult.warning) warnings.push(eventsResult.warning);

  const envelope = statusResult.parsed || {};
  const data = envelope.data || {};
  const nowMs = Date.now();

  // Latest event time per task target — heartbeat evidence for staleness.
  const lastEventMsByTask = new Map();
  for (const ev of eventsResult.events) {
    if (!ev.target_id || !ev.timestamp) continue;
    const t = Date.parse(ev.timestamp);
    if (Number.isNaN(t)) continue;
    const prev = lastEventMsByTask.get(ev.target_id);
    if (!prev || t > prev) lastEventMsByTask.set(ev.target_id, t);
  }

  const claims = (data.claims || []).map((c) => {
    const lastMs = lastEventMsByTask.get(c.task_id) || null;
    const lastActivitySeconds = lastMs !== null ? Math.round((nowMs - lastMs) / 1000) : null;
    return {
      ...c,
      last_activity_seconds: lastActivitySeconds,
      staleness: classifyClaim(c, lastActivitySeconds),
    };
  });

  return {
    generated_at: new Date(nowMs).toISOString(),
    project_dir: PROJECT_DIR,
    status_ok: envelope.ok === true,
    tasks: data.tasks || null,
    prd_status: data.prd_status || null,
    active_claims: claims.length,
    claims,
    events: eventsResult.events,
    thresholds: { quiet_seconds: QUIET_SECONDS, wedged_seconds: WEDGED_SECONDS },
    warnings,
  };
}

// ---------------------------------------------------------------------------
// HTTP server
// ---------------------------------------------------------------------------

const DASHBOARD_HTML = fs.readFileSync(path.join(__dirname, 'dashboard.html'), 'utf8');

function sendJson(res, code, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(code, {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': 'no-store',
  });
  res.end(body);
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
  if (req.method !== 'GET') {
    sendJson(res, 405, { error: 'method not allowed' });
    return;
  }
  if (url.pathname === '/') {
    res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' });
    res.end(DASHBOARD_HTML);
    return;
  }
  if (url.pathname === '/healthz') {
    sendJson(res, 200, { ok: true, pid: process.pid });
    return;
  }
  if (url.pathname === '/api/pulse') {
    try {
      const statusResult = await fetchStatus();
      const eventsResult = tailEvents(resolveEventsPath());
      sendJson(res, 200, buildPulse(statusResult, eventsResult));
    } catch (e) {
      sendJson(res, 500, { error: String((e && e.message) || e) });
    }
    return;
  }
  sendJson(res, 404, { error: 'not found' });
});

const port = Number(process.env.PULSE_PORT || 0); // 0 = random high port
server.listen(port, BIND_HOST, () => {
  const actual = server.address().port;
  // Single-line JSON contract consumed by start-server.sh — keep stable.
  process.stdout.write(
    JSON.stringify({
      event: 'server-started',
      url: `http://${URL_HOST}:${actual}/`,
      host: BIND_HOST,
      port: actual,
      pid: process.pid,
      project_dir: PROJECT_DIR,
    }) + '\n'
  );
});

// Optional owner watch: exit when the owning process dies. Off by default —
// an operator dashboard should normally outlive a single harness turn.
if (process.env.PULSE_WATCH_OWNER === '1' && process.env.PULSE_OWNER_PID) {
  const ownerPid = Number(process.env.PULSE_OWNER_PID);
  if (ownerPid > 1) {
    setInterval(() => {
      try {
        process.kill(ownerPid, 0);
      } catch (_) {
        server.close(() => process.exit(0));
        setTimeout(() => process.exit(0), 1000).unref();
      }
    }, 5000).unref();
  }
}

for (const sig of ['SIGINT', 'SIGTERM']) {
  process.on(sig, () => {
    server.close(() => process.exit(0));
    setTimeout(() => process.exit(0), 1000).unref();
  });
}
