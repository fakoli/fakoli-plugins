#!/usr/bin/env node
/**
 * anvil-pulse server — local operator dashboard for long autonomous anvil runs.
 *
 * Dependency-free (Node stdlib only). Reads anvil state two ways:
 *   1. `anvil status --json --cwd <project>`  — task rollups + per-claim
 *      phase / elapsed_seconds / lease_expires_in_seconds (retro-opps T012).
 *   2. Tail of the append-only events.jsonl — progress.noted / claim lifecycle
 *      stream (the workflow heartbeat bus). Real anvil serializes each event's
 *      payload under the `payload_json` key.
 *
 * It never writes anvil state: status is a read verb and the JSONL is opened
 * read-only. Safe next to a live run (state.db is WAL; we don't even open it).
 *
 * Environment:
 *   PULSE_PROJECT_DIR    anvil project to watch (default: cwd)
 *   PULSE_HOST           bind host (default 127.0.0.1)
 *   PULSE_URL_HOST       hostname to show in the printed URL (default localhost)
 *   PULSE_PORT           fixed port (default: random high port)
 *   PULSE_ANVIL_BIN      anvil executable (default "anvil")
 *   PULSE_STATE_DIR      explicit anvil state dir containing events.jsonl
 *                        (default: auto-discover, see resolveEventsPath)
 *   PULSE_QUIET_SECONDS  no-activity threshold for "quiet" (default 300)
 *   PULSE_WEDGED_SECONDS no-activity threshold for "possibly-wedged" (default 900)
 *   PULSE_STATUS_TTL_MS  status result cache TTL (default 2000)
 *
 * /api/pulse also accepts ?quiet_seconds=&wedged_seconds= to retune staleness
 * per request without restarting the server.
 */
'use strict';

const http = require('http');
const fs = require('fs');
const os = require('os');
const path = require('path');
const crypto = require('crypto');
const { execFile, execFileSync } = require('child_process');

const PROJECT_DIR = process.env.PULSE_PROJECT_DIR || process.cwd();
const BIND_HOST = process.env.PULSE_HOST || '127.0.0.1';
const URL_HOST = process.env.PULSE_URL_HOST || 'localhost';
const QUIET_SECONDS = Number(process.env.PULSE_QUIET_SECONDS || 300);
const WEDGED_SECONDS = Number(process.env.PULSE_WEDGED_SECONDS || 900);
const STATUS_TTL_MS = Number(process.env.PULSE_STATUS_TTL_MS || 2000);
const EVENT_TAIL_BYTES = 256 * 1024; // read at most this much from the end
const EVENT_LIMIT = 80; // newest events returned to the page

// ---------------------------------------------------------------------------
// anvil binary resolution (once, at startup)
// ---------------------------------------------------------------------------
// On Windows the anvil CLI is typically a .cmd/.exe shim (uv/pipx); Node's
// execFile cannot spawn .cmd/.bat directly (CVE-2024-27980 hardening throws
// EINVAL synchronously) and does not resolve extension-less shebang scripts.
// Resolve the real binary once via `where`, prefer a directly-spawnable .exe,
// and otherwise run the shim through cmd.exe with each argument quoted —
// argv-array spawning everywhere else. No character allowlist: paths with
// spaces, parentheses, or non-ASCII are legitimate and must work.

function resolveAnvilBin() {
  const configured = process.env.PULSE_ANVIL_BIN || 'anvil';
  if (process.platform !== 'win32') {
    return { file: configured, viaCmd: false };
  }
  if (/\.exe$/i.test(configured)) {
    return { file: configured, viaCmd: false };
  }
  try {
    const out = execFileSync('where', [configured], {
      encoding: 'utf8',
      windowsHide: true,
    });
    const candidates = out.split(/\r?\n/).filter(Boolean);
    const exe = candidates.find((c) => /\.exe$/i.test(c));
    if (exe) return { file: exe, viaCmd: false };
    if (candidates.length) return { file: candidates[0], viaCmd: true };
  } catch (_) {
    /* `where` found nothing; fall through and let spawn errors surface */
  }
  return { file: configured, viaCmd: true };
}

const ANVIL = resolveAnvilBin();

function execAnvil(args, opts, callback) {
  if (!ANVIL.viaCmd) {
    execFile(ANVIL.file, args, opts, callback);
    return;
  }
  // cmd.exe /s /c expects ONE command string; wrap every part in double
  // quotes (stripping embedded double quotes — illegal in Windows paths
  // anyway) so spaces, parentheses, and non-ASCII survive. Verbatim args are
  // required: cmd.exe does not parse MSVCRT-style quoting, so we hand it the
  // exact tail ourselves, outer-quoted per /s semantics.
  const q = (a) => '"' + String(a).replace(/"/g, '') + '"';
  const commandLine = [ANVIL.file, ...args].map(q).join(' ');
  execFile('cmd.exe', ['/d', '/s', '/c', `"${commandLine}"`], {
    ...opts,
    windowsVerbatimArguments: true,
    windowsHide: true,
  }, callback);
}

// ---------------------------------------------------------------------------
// anvil status (cached; one in-flight subprocess at a time)
// ---------------------------------------------------------------------------
// `resolvedAt` is stamped when the subprocess COMPLETES, not when it is
// dispatched, and a pending promise is always reused — so a slow anvil call
// can never stack a second subprocess behind it, and the TTL measures real
// result freshness.

let statusCache = { resolvedAt: 0, promise: null, pending: false };

function fetchStatus() {
  const now = Date.now();
  if (
    statusCache.promise &&
    (statusCache.pending || now - statusCache.resolvedAt < STATUS_TTL_MS)
  ) {
    return statusCache.promise;
  }
  statusCache.pending = true;
  statusCache.promise = new Promise((resolve) => {
    const args = ['status', '--json', '--cwd', PROJECT_DIR];
    const opts = { timeout: 15000, windowsHide: true, maxBuffer: 4 * 1024 * 1024 };
    execAnvil(args, opts, (err, stdout) => {
      statusCache.pending = false;
      statusCache.resolvedAt = Date.now();
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
    });
  });
  return statusCache.promise;
}

// ---------------------------------------------------------------------------
// events.jsonl discovery + tail
// ---------------------------------------------------------------------------

// Mirror of anvil's _workspace_key (bin/src/anvil/cli/_helpers.py): a slug of
// the project basename plus sha256(abs_path)[:8]. Lets us pick the workspace
// that actually belongs to PROJECT_DIR instead of guessing by mtime.
function workspaceKeyCandidates(projectDir) {
  const base = path.basename(projectDir) || 'project';
  const slug = base.replace(/[^A-Za-z0-9_-]/g, '-') || 'project';
  // anvil hashes str(Path(root)) — a native path. Hash the plausible
  // canonical spellings so separator/trailing-slash differences don't miss.
  const spellings = new Set();
  const native = path.resolve(projectDir);
  spellings.add(native);
  if (process.platform === 'win32') {
    spellings.add(native.replace(/\//g, '\\'));
  }
  const keys = new Set();
  for (const s of spellings) {
    const digest = crypto.createHash('sha256').update(s, 'utf8').digest('hex').slice(0, 8);
    keys.add(`${slug}-${digest}`);
  }
  keys.add(slug); // legacy layout: workspaces/<basename> with no hash suffix
  return { slug, keys };
}

let eventsPathCache = { at: 0, path: null, warning: null };
const EVENTS_PATH_TTL_MS = 30000;

function resolveEventsPath() {
  if (process.env.PULSE_STATE_DIR) {
    return { path: path.join(process.env.PULSE_STATE_DIR, 'events.jsonl'), warning: null };
  }
  const now = Date.now();
  if (eventsPathCache.at && now - eventsPathCache.at < EVENTS_PATH_TTL_MS) {
    return eventsPathCache;
  }
  const resolved = discoverEventsPath();
  eventsPathCache = { ...resolved, at: now };
  return resolved;
}

function discoverEventsPath() {
  // In-repo state dirs (ANVIL_STATE_LAYOUT=local / legacy) — exact, check first.
  const local = [
    path.join(PROJECT_DIR, '.anvil', 'events.jsonl'),
    path.join(PROJECT_DIR, 'bin', '.anvil', 'events.jsonl'),
  ];
  for (const p of local) {
    if (fs.existsSync(p)) return { path: p, warning: null };
  }
  // HOME workspace layout: ~/.anvil/workspaces/<slug>-<sha8>/.anvil/events.jsonl
  const wsRoot = path.join(os.homedir(), '.anvil', 'workspaces');
  const { slug, keys } = workspaceKeyCandidates(PROJECT_DIR);
  for (const key of keys) {
    const p = path.join(wsRoot, key, '.anvil', 'events.jsonl');
    if (fs.existsSync(p)) return { path: p, warning: null };
  }
  // Last resort: same-slug prefix match (covers canonicalization drift between
  // this mirror and anvil's own hashing). Explicitly warned — could be a
  // different checkout of a same-named project.
  try {
    const matches = fs
      .readdirSync(wsRoot)
      .filter((e) => e === slug || e.startsWith(slug + '-'))
      .map((e) => path.join(wsRoot, e, '.anvil', 'events.jsonl'))
      .filter((p) => fs.existsSync(p));
    if (matches.length === 1) {
      return {
        path: matches[0],
        warning: `events.jsonl matched by project name only (${path.basename(path.dirname(path.dirname(matches[0])))}); set PULSE_STATE_DIR if this is the wrong checkout`,
      };
    }
    if (matches.length > 1) {
      return {
        path: null,
        warning: `multiple workspaces match project name '${slug}'; set PULSE_STATE_DIR to disambiguate — event feed disabled`,
      };
    }
  } catch (_) {
    /* no workspace root */
  }
  return {
    path: null,
    warning:
      'events.jsonl not found (set PULSE_STATE_DIR to the anvil state dir); event feed disabled',
  };
}

// Tail cache: skip the 256KB read + parse entirely when the file has not
// grown since the last request (size+mtime key) — polls are cheap reads of
// an unchanged file most of the time.
let tailCache = { key: '', result: null };

function tailEvents(resolved) {
  const out = { events: [], warning: resolved.warning };
  const eventsPath = resolved.path;
  if (!eventsPath) return out;
  let fd;
  try {
    fd = fs.openSync(eventsPath, 'r');
    const st = fs.fstatSync(fd);
    const cacheKey = `${eventsPath}|${st.size}|${st.mtimeMs}`;
    if (tailCache.key === cacheKey && tailCache.result) {
      return { events: tailCache.result, warning: resolved.warning };
    }
    const start = Math.max(0, st.size - EVENT_TAIL_BYTES);
    const buf = Buffer.alloc(st.size - start);
    fs.readSync(fd, buf, 0, buf.length, start);
    const lines = buf.toString('utf8').split('\n');
    if (start > 0) lines.shift(); // first line may be a partial record
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      try {
        const ev = JSON.parse(trimmed);
        // Real anvil serializes the payload as `payload_json`; accept
        // `payload` too for forward/hand-rolled compatibility.
        const payload = ev.payload_json || ev.payload || {};
        out.events.push({
          timestamp: ev.timestamp || null,
          action: ev.action || null,
          actor: ev.actor || null,
          target_id: ev.target_id || null,
          phase: payload.phase || null,
          notes: payload.detail || payload.notes || null,
        });
      } catch (_) {
        /* skip malformed line */
      }
    }
    out.events = out.events.slice(-EVENT_LIMIT).reverse(); // newest first
    tailCache = { key: cacheKey, result: out.events };
  } catch (e) {
    out.warning = `could not read ${eventsPath}: ${e.code || e.message}`;
  } finally {
    if (fd !== undefined) fs.closeSync(fd);
  }
  return out;
}

// ---------------------------------------------------------------------------
// staleness classification (the folded-in stuck-detector)
// ---------------------------------------------------------------------------

function classifyClaim(claim, lastActivitySeconds, thresholds) {
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
  if (age < thresholds.quiet) return 'healthy';
  if (age < thresholds.wedged) return 'quiet';
  return 'possibly-wedged';
}

function buildPulse(statusResult, eventsResult, thresholds) {
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
      staleness: classifyClaim(c, lastActivitySeconds, thresholds),
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
    thresholds: { quiet_seconds: thresholds.quiet, wedged_seconds: thresholds.wedged },
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

function thresholdsFrom(url) {
  const num = (name, fallback) => {
    const v = Number(url.searchParams.get(name));
    return Number.isFinite(v) && v > 0 ? v : fallback;
  };
  return {
    quiet: num('quiet_seconds', QUIET_SECONDS),
    wedged: num('wedged_seconds', WEDGED_SECONDS),
  };
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
      sendJson(res, 200, buildPulse(statusResult, eventsResult, thresholdsFrom(url)));
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

for (const sig of ['SIGINT', 'SIGTERM']) {
  process.on(sig, () => {
    server.close(() => process.exit(0));
    setTimeout(() => process.exit(0), 1000).unref();
  });
}
