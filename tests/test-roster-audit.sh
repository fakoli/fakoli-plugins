#!/usr/bin/env bash
#
# test-roster-audit.sh — guards for scripts/roster-audit.py (roster prune audit).
#
# Builds a synthetic roster root in a temp dir and asserts the classification
# rules. Fully offline: no real ~/.claude, no network, no session transcripts —
# the usage side is an injected session-report-shaped JSON fixture.
#
# The dependency guard is the rule most likely to regress into a wrong prune
# (archiving a unit another unit still points at), so it gets its own case:
# `dep-target` is never used but IS referenced, and must classify KEEP.
#
# Usage: ./tests/test-roster-audit.sh   (exit 0 on full PASS)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
AUDIT="$ROOT_DIR/scripts/roster-audit.py"

PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null 2>&1 || PY=python

PASS_COUNT=0
FAIL_COUNT=0
pass() { echo "  PASS $1"; PASS_COUNT=$((PASS_COUNT + 1)); }
fail() { echo "  FAIL $1"; FAIL_COUNT=$((FAIL_COUNT + 1)); }

FIXTURE="$(mktemp -d)"
trap 'rm -rf "$FIXTURE"' EXIT

TODAY="2026-08-08"

mk_skill() {
  # mk_skill <dir> <name> <description> <body>
  mkdir -p "$1/$2"
  {
    echo "---"
    echo "name: $2"
    echo "description: $3"
    echo "---"
    echo ""
    echo "$4"
  } > "$1/$2/SKILL.md"
}

# --- global skills -----------------------------------------------------------
GS="$FIXTURE/skills"
mk_skill "$GS" "used-skill"  "A skill that gets invoked."            "body"
mk_skill "$GS" "dead-skill"  "A skill nobody has ever invoked."      "body"
mk_skill "$GS" "dep-target"  "Never invoked, but another unit cites it." "body"
mk_skill "$GS" "citing-skill" "Cites the dependency target."         "See dep-target for details."
mk_skill "$GS" "guarded-skill" "Never invoked, protected by flag."   "body"
mk_skill "$GS" "fresh-skill" "Never invoked, but brand new."         "body"
# A unit named for a common English word. Other bodies use that word in prose;
# that must NOT register as a dependency, or any suite named `update`/`analyze`
# becomes permanently unprunable.
mk_skill "$GS" "update" "Never invoked; its name is an ordinary word." "body"
mk_skill "$GS" "prose-skill" "Mentions the word update in plain prose." \
  "Remember to update the changelog and analyze the results before shipping."

# Age every skill well past the --new-days window, then make one genuinely new.
"$PY" - "$GS" <<'EOF'
import os, sys, time
root = sys.argv[1]
old = time.time() - 400 * 86400
for name in os.listdir(root):
    path = os.path.join(root, name, "SKILL.md")
    stamp = time.time() if name == "fresh-skill" else old
    os.utime(path, (stamp, stamp))
EOF

# --- a plugin: two skills that cite ONLY each other --------------------------
# Names are >= MIN_BARE_NAME_LEN and the bodies also use the namespaced form, so
# an edge genuinely forms unless scan_dependencies() excludes intra-unit pairs.
# (With short names like "alpha"/"beta" no edge forms at all and the exclusion
# goes untested — a mutation to it would survive.)
PV="$FIXTURE/plugins/cache/testmarket/deadplugin/1.0.0"
mkdir -p "$PV/skills"
mk_skill "$PV/skills" "alphaone" "First skill of the dead plugin." \
  "Pairs with deadplugin:betatwo — see betatwo for the second half."
mk_skill "$PV/skills" "betatwo"  "Second skill of the dead plugin." \
  "Pairs with deadplugin:alphaone — see alphaone for the first half."

# --- a plugin present on disk but not enabled --------------------------------
DV="$FIXTURE/plugins/cache/testmarket/offplugin/1.0.0"
mkdir -p "$DV/skills"
mk_skill "$DV/skills" "gamma" "A skill in a disabled plugin." "body"

"$PY" - "$FIXTURE" <<'EOF'
import os, sys, time
old = time.time() - 400 * 86400
for base, _, files in os.walk(os.path.join(sys.argv[1], "plugins")):
    for f in files:
        p = os.path.join(base, f)
        os.utime(p, (old, old))
EOF

cat > "$FIXTURE/settings.json" <<'EOF'
{
  "enabledPlugins": {
    "deadplugin@testmarket": true,
    "offplugin@testmarket": false
  }
}
EOF

# --- a second install mechanism: a directory of plugin roots -----------------
# The desktop app materialises plugins this way; auditing only the CLI cache
# measures half the roster.
ALT="$FIXTURE/rpm"
mkdir -p "$ALT/plugin_abc/skills"
echo '{"name": "deskplugin", "version": "1.0.0"}' > "$ALT/plugin_abc/plugin.json"
mk_skill "$ALT/plugin_abc/skills" "delta" "A skill from the desktop install root." "body"

# Same plugin name as a CLI-cache unit: a session lists it once, so the
# deduplicated total must not count both copies.
mkdir -p "$ALT/plugin_dup/skills"
echo '{"name": "deadplugin", "version": "1.0.0"}' > "$ALT/plugin_dup/plugin.json"
# This copy cites the CLI-cache copy's skill by its namespaced id. A plugin
# citing its own twin is not a dependency — if it counted, no duplicated plugin
# could ever be nominated.
mk_skill "$ALT/plugin_dup/skills" "alphaone" "First skill of the dead plugin." \
  "Pairs with deadplugin:betatwo."

# A manifest dates the plugins. Files are re-materialised on every launch, so
# their mtimes are always "today" — without the manifest date, --new-days would
# protect this whole root.
cat > "$ALT/manifest.json" <<'EOF'
{
  "plugins": [
    {"id": "plugin_abc", "name": "deskplugin", "updatedAt": "2025-01-15T00:00:00Z"},
    {"id": "plugin_dup", "name": "deadplugin", "updatedAt": "2025-01-15T00:00:00Z"}
  ]
}
EOF

# NOTE: the files under $ALT are deliberately left with fresh mtimes, exactly as
# the desktop app leaves them after re-materialising on launch. Their age must
# come from manifest.json alone.

# session-report-shaped usage fixture: only used-skill has invocations.
cat > "$FIXTURE/usage.json" <<'EOF'
{
  "by_skill": { "used-skill": { "api_calls": 12 } },
  "overall": { "skill_invocations": { "used-skill": 3 } },
  "by_subagent_type": {}
}
EOF

echo "== roster-audit.py guards =="

# 1. script exists
if [[ -f "$AUDIT" ]]; then pass "script exists"
else fail "scripts/roster-audit.py missing"; exit 1; fi

# 2. runs against the fixture and emits JSON
OUT="$FIXTURE/out.json"
if "$PY" "$AUDIT" --roster-root "$FIXTURE" --usage "$FIXTURE/usage.json" \
     --plugin-root "$ALT" --protect guarded-skill --today "$TODAY" --json > "$OUT" 2>"$FIXTURE/err"; then
  pass "runs against fixture roster"
else
  fail "run failed: $(cat "$FIXTURE/err")"; exit 1
fi

bucket_of() {
  "$PY" - "$OUT" "$1" <<'EOF'
import json, sys
data = json.load(open(sys.argv[1]))
for unit in data["units"]:
    if unit["unit"] == sys.argv[2]:
        print(unit["bucket"]); break
else:
    print("MISSING")
EOF
}

field_of() {
  "$PY" - "$OUT" "$1" "$2" <<'EOF'
import json, sys
data = json.load(open(sys.argv[1]))
for unit in data["units"]:
    if unit["unit"] == sys.argv[2]:
        print(unit[sys.argv[3]]); break
else:
    print("MISSING")
EOF
}

expect_bucket() {
  # expect_bucket <unit> <expected> <label>
  got="$(bucket_of "$1")"
  if [[ "$got" == "$2" ]]; then pass "$3"
  else fail "$3 (unit '$1' expected $2, got $got)"; fi
}

# 3. the classification rules
expect_bucket "used-skill"           "KEEP"      "used unit is kept"
expect_bucket "dead-skill"           "CANDIDATE" "unused, unreferenced, old unit is nominated"
expect_bucket "dep-target"           "KEEP"      "unused but referenced unit is kept (dependency guard)"
expect_bucket "guarded-skill"        "KEEP"      "protected unit is kept"
expect_bucket "fresh-skill"          "KEEP"      "unit newer than --new-days is kept"
expect_bucket "offplugin@testmarket" "KEEP"      "disabled plugin is kept (costs nothing)"

expect_bucket "update" "CANDIDATE" "a bare common word in prose is not a dependency"

# 4. the dependency edge is real, and names the citing unit
refs="$(field_of "dep-target" "referenced_by")"
if grep -q "citing-skill" <<<"$refs"; then pass "dependency edge names the citing unit"
else fail "dep-target referenced_by missing citing-skill (got: $refs)"; fi

# 5. intra-plugin sibling references must NOT count as a dependency —
#    otherwise every multi-skill plugin is permanently unprunable.
expect_bucket "deadplugin@testmarket" "CANDIDATE" "sibling-only references do not block a plugin"
prefs="$(field_of "deadplugin@testmarket" "referenced_by")"
if [[ "$prefs" == "[]" ]]; then pass "intra-unit references are excluded"
else fail "deadplugin picked up intra-unit edges: $prefs"; fi

# 6. a plugin is one unit, not one unit per skill
count="$(field_of "deadplugin@testmarket" "entry_count")"
if [[ "$count" == "2" ]]; then pass "plugin groups its skills into one unit"
else fail "expected 2 entries in deadplugin unit, got $count"; fi

# 7. usage counts both the bare and namespaced form
uses="$(field_of "used-skill" "uses")"
if [[ "$uses" == "15" ]]; then pass "usage sums by_skill and skill_invocations (12+3)"
else fail "expected uses=15 for used-skill, got $uses"; fi

# 8. --plugin-root picks up the second install mechanism, named from plugin.json
expect_bucket "deskplugin@rpm" "CANDIDATE" "--plugin-root discovers desktop-style plugins"
dcount="$(field_of "deskplugin@rpm" "entry_count")"
if [[ "$dcount" == "1" ]]; then pass "desktop plugin contributes its entries"
else fail "expected 1 entry in deskplugin unit, got $dcount"; fi

# 8b. the manifest date wins over the always-fresh file mtime
age="$(field_of "deskplugin@rpm" "age_days")"
if [[ "$age" -gt 30 ]]; then pass "manifest updatedAt dates the unit ($age d), not the file mtime"
else fail "expected manifest-derived age > 30d, got $age"; fi

# 8c. a plugin present under two roots is counted once in the deduped total
"$PY" - "$OUT" <<'EOF'
import json, sys
totals = json.load(open(sys.argv[1]))["totals"]
raw, dedup = totals["cost_tokens"], totals["deduped_cost_tokens"]
assert dedup < raw, f"deduped {dedup} should be below raw {raw}"
assert totals["deduped_units"] < totals["units"], "deduped unit count should drop"
EOF
if [[ $? -eq 0 ]]; then pass "duplicate plugin counted once in deduped totals"
else fail "dedup totals did not collapse the duplicate"; fi

# 9. markdown mode renders and reports the candidate
if "$PY" "$AUDIT" --roster-root "$FIXTURE" --usage "$FIXTURE/usage.json" \
     --today "$TODAY" 2>/dev/null | grep -q "dead-skill"; then
  pass "markdown report lists the candidate"
else fail "markdown report missing candidate"; fi

# 9. error paths
"$PY" "$AUDIT" >/dev/null 2>&1 && fail "missing args should error" || pass "missing args errors"
"$PY" "$AUDIT" --roster-root "$FIXTURE/nope" >/dev/null 2>&1 \
  && fail "bad roster root should error" || pass "bad roster root errors"

# 10. no usage file: nothing is treated as used, but nothing crashes
if "$PY" "$AUDIT" --roster-root "$FIXTURE" --today "$TODAY" --json > "$OUT" 2>/dev/null; then
  if [[ "$(bucket_of "used-skill")" == "CANDIDATE" ]]; then
    pass "without --usage, previously-used unit falls back to candidate"
  else fail "expected used-skill to be CANDIDATE without usage data"; fi
else fail "run without --usage failed"; fi

echo "========================================"
echo "  Passed: $PASS_COUNT"
echo "  Failed: $FAIL_COUNT"
echo "========================================"
[[ $FAIL_COUNT -eq 0 ]]
