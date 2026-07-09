#!/usr/bin/env bash
# Hermetic smoke test for the anvil-pulse server.
# Uses a fake `anvil` shim + fixture events.jsonl — no real anvil install needed.
# Requires: node, bash, curl (or node-based fetch fallback), python3.
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TMP="$SCRIPT_DIR/.tmp"
rm -rf "$TMP"
mkdir -p "$TMP/bin" "$TMP/project/.anvil"

fail() { echo "FAIL: $1"; cleanup; exit 1; }
PASS_COUNT=0
pass() { echo "ok - $1"; PASS_COUNT=$((PASS_COUNT + 1)); }

SERVER_PID=""
cleanup() {
  [[ -n "$SERVER_PID" ]] && kill "$SERVER_PID" 2>/dev/null
}
trap cleanup EXIT

# --- fixture: fake anvil CLI ------------------------------------------------
# Single source of truth (anvil.js) with bash + .cmd wrappers so the shim is
# executable on POSIX AND from Node's win32 shell fallback (cmd.exe resolves
# anvil.cmd via PATHEXT; execFile can't run shebang scripts there).
# The JSON served lives in status.json so scenarios swap without new shims.
cat > "$TMP/bin/anvil.js" <<'SHIM'
const fs = require('fs');
const path = require('path');
if (process.argv.includes('status')) {
  process.stdout.write(fs.readFileSync(path.join(__dirname, 'status.json'), 'utf8'));
  process.exit(0);
}
process.stdout.write('{"ok": false}');
process.exit(1);
SHIM
cat > "$TMP/bin/anvil" <<'SHIM'
#!/usr/bin/env bash
exec node "$(dirname "$0")/anvil.js" "$@"
SHIM
chmod +x "$TMP/bin/anvil"
printf '@echo off\r\nnode "%%~dp0anvil.js" %%*\r\n' > "$TMP/bin/anvil.cmd"

# Scenario 1: elapsed 100s / lease 500s, one claim healthy (recent event), one silent.
cat > "$TMP/bin/status.json" <<'JSON'
{"ok": true, "command": "status", "data": {
  "prd_status": "approved",
  "tasks": {"total": 10, "ready": 2, "claimed": 2, "in_progress": 2, "needs_review": 1, "blocked": 0, "done": 5},
  "active_claims": 2,
  "claims": [
    {"claim_id": "c1", "task_id": "T001", "actor": "loop-a", "phase": "implement", "elapsed_seconds": 100, "lease_expires_in_seconds": 500},
    {"claim_id": "c2", "task_id": "T002", "actor": "loop-b", "phase": null, "elapsed_seconds": 2000, "lease_expires_in_seconds": 900}
  ]
}}
JSON

# --- fixture: events.jsonl ---------------------------------------------------
# T001 has a fresh progress.noted event; T002 has nothing (silent -> stale path).
python3 - "$TMP/project/.anvil/events.jsonl" <<'PY'
import json, sys, datetime
now = datetime.datetime.now(datetime.timezone.utc)
# Append order = chronological (events.jsonl is append-only): oldest first.
# Payload key is payload_json — the key REAL anvil writes (Event.payload_json,
# verified on disk). A fixture using "payload" would mask a contract mismatch.
lines = [
    {"id": "e0", "timestamp": (now - datetime.timedelta(seconds=3000)).isoformat(),
     "actor": "loop-b", "action": "claim.created", "target_kind": "task",
     "target_id": "T002", "payload_json": {}},
    {"id": "e1", "timestamp": (now - datetime.timedelta(seconds=30)).isoformat(),
     "actor": "loop-a", "action": "progress.noted", "target_kind": "task",
     "target_id": "T001", "payload_json": {"phase": "implement", "notes": "writing parser"}},
]
with open(sys.argv[1], "w", encoding="utf-8") as f:
    for l in lines:
        f.write(json.dumps(l) + "\n")
    f.write('{"broken json line\n')  # malformed line must be skipped, not fatal
PY

# --- start server ------------------------------------------------------------
# Pin the shim via PULSE_ANVIL_BIN — on Windows, PATH resolution would find a
# real anvil.exe before our extension-less shim. Node needs Windows-style
# paths, so convert MSYS paths when cygpath is available (Git Bash).
if command -v cygpath >/dev/null 2>&1; then
  ANVIL_SHIM="$(cygpath -m "$TMP/bin/anvil.cmd")"
  PROJECT_ARG="$(cygpath -m "$TMP/project")"
else
  ANVIL_SHIM="$TMP/bin/anvil"
  PROJECT_ARG="$TMP/project"
fi
PORT=$((20000 + RANDOM % 20000))
env PULSE_ANVIL_BIN="$ANVIL_SHIM" PULSE_PROJECT_DIR="$PROJECT_ARG" PULSE_PORT="$PORT" \
    PULSE_QUIET_SECONDS=300 PULSE_WEDGED_SECONDS=900 \
    node "$PLUGIN_DIR/scripts/server.cjs" > "$TMP/server.log" 2>&1 &
SERVER_PID=$!

for _ in $(seq 1 50); do
  grep -q "server-started" "$TMP/server.log" 2>/dev/null && break
  kill -0 "$SERVER_PID" 2>/dev/null || { cat "$TMP/server.log"; fail "server died on startup"; }
  sleep 0.1
done
grep -q "server-started" "$TMP/server.log" || fail "server did not start in 5s"
pass "server starts and prints server-started"

fetch() { curl -sf "http://127.0.0.1:$PORT$1" 2>/dev/null; }

# --- healthz -----------------------------------------------------------------
fetch /healthz | grep -q '"ok":true' || fail "/healthz not ok"
pass "/healthz responds"

# --- dashboard HTML ----------------------------------------------------------
fetch / | grep -q "anvil pulse" || fail "/ did not serve the dashboard"
pass "/ serves dashboard HTML"

# --- /api/pulse: shape + enrichment -------------------------------------------
fetch /api/pulse > "$TMP/pulse.json" || fail "/api/pulse failed"
python3 - "$TMP/pulse.json" <<'PY' || fail "/api/pulse assertions failed"
import json, sys
p = json.load(open(sys.argv[1], encoding="utf-8"))
assert p["status_ok"] is True, "status_ok"
assert p["tasks"]["ready"] == 2, "task rollup passthrough"
claims = {c["task_id"]: c for c in p["claims"]}
assert set(claims) == {"T001", "T002"}, "both claims present"
# T001: fresh event 30s ago -> healthy, last_activity_seconds populated
assert claims["T001"]["staleness"] == "healthy", claims["T001"]["staleness"]
assert claims["T001"]["last_activity_seconds"] is not None
assert claims["T001"]["last_activity_seconds"] < 300
# T002: last event 3000s ago, lease alive -> possibly-wedged
assert claims["T002"]["staleness"] == "possibly-wedged", claims["T002"]["staleness"]
# events newest-first, malformed line skipped
assert len(p["events"]) == 2, f"expected 2 events, got {len(p['events'])}"
assert p["events"][0]["action"] == "progress.noted", "newest first"
assert p["events"][0]["phase"] == "implement"
print("pulse payload assertions passed")
PY
pass "/api/pulse enriches claims + classifies staleness + skips malformed lines"

# --- 404 ---------------------------------------------------------------------
code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$PORT/nope")
[[ "$code" == "404" ]] || fail "expected 404 for unknown path, got $code"
pass "unknown path returns 404"

# --- lease-expired classification ---------------------------------------------
cat > "$TMP/bin/status.json" <<'JSON'
{"ok": true, "command": "status", "data": {
  "tasks": {"total": 1, "ready": 0, "claimed": 1, "in_progress": 1, "needs_review": 0, "blocked": 0, "done": 0},
  "active_claims": 1,
  "claims": [
    {"claim_id": "c3", "task_id": "T003", "actor": "loop-c", "phase": "verify", "elapsed_seconds": 50, "lease_expires_in_seconds": -60}
  ]
}}
JSON
sleep 2.2  # let the status cache TTL (2s) lapse
fetch /api/pulse > "$TMP/pulse2.json" || fail "/api/pulse (second) failed"
python3 -c '
import json, sys
p = json.load(open(sys.argv[1], encoding="utf-8"))
c = p["claims"][0]
assert c["staleness"] == "lease-expired", c["staleness"]
print("lease-expired assertion passed")
' "$TMP/pulse2.json" || fail "lease-expired classification"
pass "expired lease classified lease-expired (overrides activity)"

# --- HOME-workspace discovery (correct depth + project-keyed match) -----------
# Real layout: ~/.anvil/workspaces/<slug>-<sha256(abs_path)[:8]>/.anvil/events.jsonl
kill "$SERVER_PID" 2>/dev/null; wait "$SERVER_PID" 2>/dev/null; SERVER_PID=""
mkdir -p "$TMP/project2" "$TMP/home"
if command -v cygpath >/dev/null 2>&1; then
  PROJECT2_ARG="$(cygpath -m "$TMP/project2")"
  HOME_ARG="$(cygpath -m "$TMP/home")"
else
  PROJECT2_ARG="$TMP/project2"
  HOME_ARG="$TMP/home"
fi
# Compute the workspace key exactly as server.cjs does (path.resolve + sha256).
WSKEY=$(node -e '
const c = require("crypto"), p = require("path");
const d = p.resolve(process.argv[1]);
const slug = (p.basename(d).replace(/[^A-Za-z0-9_-]/g, "-")) || "project";
console.log(slug + "-" + c.createHash("sha256").update(d, "utf8").digest("hex").slice(0, 8));
' "$PROJECT2_ARG")
mkdir -p "$TMP/home/.anvil/workspaces/$WSKEY/.anvil"
# Decoy: another workspace with a NEWER file that must NOT be picked.
mkdir -p "$TMP/home/.anvil/workspaces/other-deadbeef/.anvil"
python3 - "$TMP/home/.anvil/workspaces/$WSKEY/.anvil/events.jsonl" <<'PY'
import json, sys, datetime
now = datetime.datetime.now(datetime.timezone.utc)
with open(sys.argv[1], "w", encoding="utf-8") as f:
    f.write(json.dumps({"id": "w1", "timestamp": (now - datetime.timedelta(seconds=10)).isoformat(),
        "actor": "loop-w", "action": "progress.noted", "target_kind": "task",
        "target_id": "T010", "payload_json": {"phase": "verify"}}) + "\n")
PY
printf '{"id":"x1","timestamp":"2999-01-01T00:00:00Z","actor":"x","action":"progress.noted","target_kind":"task","target_id":"TXXX","payload_json":{"phase":"decoy"}}\n' \
  > "$TMP/home/.anvil/workspaces/other-deadbeef/.anvil/events.jsonl"
touch "$TMP/home/.anvil/workspaces/other-deadbeef/.anvil/events.jsonl"

PORT2=$((20000 + RANDOM % 20000))
env PULSE_ANVIL_BIN="$ANVIL_SHIM" PULSE_PROJECT_DIR="$PROJECT2_ARG" PULSE_PORT="$PORT2" \
    HOME="$HOME_ARG" USERPROFILE="$HOME_ARG" \
    node "$PLUGIN_DIR/scripts/server.cjs" > "$TMP/server2.log" 2>&1 &
SERVER_PID=$!
for _ in $(seq 1 50); do
  grep -q "server-started" "$TMP/server2.log" 2>/dev/null && break
  sleep 0.1
done
curl -sf "http://127.0.0.1:$PORT2/api/pulse" > "$TMP/pulse3.json" || fail "/api/pulse (workspace) failed"
python3 -c '
import json, sys
p = json.load(open(sys.argv[1], encoding="utf-8"))
actions = [e["target_id"] for e in p["events"]]
assert "T010" in actions, f"workspace events not found: {actions}"
assert "TXXX" not in actions, "decoy workspace was selected instead of the project-keyed one"
assert not any("events.jsonl not found" in w for w in p["warnings"]), p["warnings"]
print("workspace discovery assertions passed")
' "$TMP/pulse3.json" || fail "workspace-layout discovery"
pass "HOME-workspace discovery finds project-keyed events at the real depth"

cleanup
SERVER_PID=""
echo
echo "ALL $PASS_COUNT TESTS PASSED"
