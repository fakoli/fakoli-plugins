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
# An unhyphenated name genuinely cited in prose. The strict rule cannot see it
# (that is the documented trade), so it must appear as a WEAK reference.
mk_skill "$GS" "oneword" "Unhyphenated name, genuinely depended on." "body"
# Referenced only from inside a fenced code block — a sample, not a citation.
mk_skill "$GS" "fenced-target" "Cited only inside a code fence." "body"
# Referenced only as a markdown link path — a URL, not a slash command.
mk_skill "$GS" "linked-target" "Cited only as a markdown link path." "body"

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

# A plugin whose FILES are old but which installed_plugins.json says was
# updated recently. Its age must come from the manifest, so it is kept as new.
FV="$FIXTURE/plugins/cache/testmarket/freshplugin/1.0.0"
mkdir -p "$FV/skills"
mk_skill "$FV/skills" "epsilon" "A recently installed plugin with old files." "body"

# A plugin sharing a bare name with the used global skill, to prove the exact-id
# usage match is not also credited here.
NV="$FIXTURE/plugins/cache/testmarket/namesake/1.0.0"
mkdir -p "$NV/skills"
mk_skill "$NV/skills" "used-skill" "Shares a bare name with the global skill." "body"

# A plugin holding a skill AND a command of the same name: two entries, one id.
TV="$FIXTURE/plugins/cache/testmarket/twins/1.0.0"
mkdir -p "$TV/skills" "$TV/commands"
mk_skill "$TV/skills" "shared" "Skill half of the id collision." "body"
printf -- '---\nname: shared\ndescription: Command half of the id collision.\n---\n\nbody\n' \
  > "$TV/commands/shared.md"

"$PY" - "$FIXTURE/plugins" <<'EOF'
import os, sys, time
old = time.time() - 400 * 86400
for base, _, files in os.walk(sys.argv[1]):
    for f in files:
        p = os.path.join(base, f)
        os.utime(p, (old, old))
EOF

cat > "$FIXTURE/settings.json" <<'EOF'
{
  "enabledPlugins": {
    "deadplugin@testmarket": true,
    "offplugin@testmarket": false,
    "freshplugin@testmarket": true,
    "namesake@testmarket": true,
    "twins@testmarket": true
  }
}
EOF

cat > "$FIXTURE/plugins/installed_plugins.json" <<'EOF'
{
  "version": 2,
  "plugins": {
    "freshplugin@testmarket": [
      {"version": "1.0.0", "installedAt": "2026-08-01T00:00:00.000Z",
       "lastUpdated": "2020-01-01T00:00:00.000Z"}
    ]
  }
}
EOF

echo '[]' > "$FIXTURE/wrong-shape.json"

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
  "by_skill": { "used-skill": { "api_calls": 12 }, "twins:shared": { "api_calls": 10 } },
  "overall": { "skill_invocations": { "used-skill": 3 } },
  "by_subagent_type": {}
}
EOF

# An unclosed frontmatter fence must warn rather than silently zero the cost.
mkdir -p "$GS/broken-fence"
printf -- '---\nname: broken-fence\ndescription: Never closed.\n\nbody\n' \
  > "$GS/broken-fence/SKILL.md"

# Bodies that must NOT create edges: a fenced sample and a markdown link.
mk_skill "$GS" "fence-citer" "Prints a sample containing another unit name." \
  '```
$ run fenced-target --now
```'
mk_skill "$GS" "link-citer" "Links to a path that looks like a command." \
  "See [the docs](/linked-target) for background."
mk_skill "$GS" "word-citer" "Genuinely depends on an unhyphenated unit." \
  "Load the oneword skill first for shared context."

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
data = json.load(open(sys.argv[1]))
totals = data["totals"]
raw, loaded = totals["cost_tokens"], totals["loaded_cost_tokens"]
assert loaded < raw, f"loaded {loaded} should be below raw {raw}"
assert totals["loaded_units"] < totals["units"], "loaded unit count should drop"

# Recompute the loaded figure independently: max cost per plugin name across
# enabled, non-project units only. A disabled unit contributing anything would
# make disabling it show a zero delta on re-measure.
expected = {}
for u in data["units"]:
    if not u["enabled"] or u["scope"] == "project":
        continue
    name = u["unit"].split("@")[0]
    expected[name] = max(expected.get(name, 0), u["cost_tokens_est"])
assert loaded == sum(expected.values()), \
    f"loaded {loaded} != recomputed {sum(expected.values())}"
assert totals["loaded_units"] == len(expected), "loaded unit count mismatch"

off = next(u for u in data["units"] if u["unit"] == "offplugin@testmarket")
assert off["cost_tokens_est"] > 0, "fixture disabled plugin should have a cost"
assert "offplugin" not in expected, "disabled plugin contributed to the loaded total"
EOF
if [[ $? -eq 0 ]]; then pass "loaded total excludes duplicates and disabled units"
else fail "loaded totals did not exclude duplicate/disabled cost"; fi

# 8c-ii. CLI-cache plugins are aged from installed_plugins.json, not file mtime
if [[ "$(field_of "freshplugin@testmarket" "age_days")" -lt 30 ]]; then
  pass "CLI-cache plugin aged from installed_plugins.json"
else fail "expected freshplugin age < 30d from installed_plugins.json, got $(field_of "freshplugin@testmarket" "age_days")"; fi
expect_bucket "freshplugin@testmarket" "KEEP" "recently installed CLI plugin is kept as new"

# 8d. a real dependency on an UNHYPHENATED name is missed by the strict rule,
#     so it must still surface as a weak reference rather than vanishing.
weak="$(field_of "oneword" "weak_referenced_by")"
if grep -q "word-citer" <<<"$weak"; then pass "unhyphenated prose reference surfaces as weak"
else fail "expected 'oneword' weak_referenced_by to name word-citer (got: $weak)"; fi
expect_bucket "oneword" "CANDIDATE" "a weak reference does not classify as a dependency"

# 8e. a reference inside a fenced code block is a sample, not a citation
expect_bucket "fenced-target" "CANDIDATE" "reference inside a code fence is not a dependency"

# 8f. a markdown link path is not a slash command
expect_bucket "linked-target" "CANDIDATE" "markdown link path is not a command reference"

# 8g. version directories sort numerically, not lexicographically
if "$PY" - <<'EOF'
import importlib.util, pathlib, sys
spec = importlib.util.spec_from_file_location("ra", pathlib.Path("scripts/roster-audit.py"))
ra = importlib.util.module_from_spec(spec); spec.loader.exec_module(ra)
order = sorted(["1.2.0", "1.10.0", "1.9.0", "unknown"], key=ra.version_key)
assert order[-1] == "1.10.0", order
EOF
then pass "version dirs sort numerically (1.10.0 > 1.9.0)"
else fail "version_key sorted lexicographically"; fi

# 8h. a usage file that is valid JSON but the wrong shape must not traceback
if out="$("$PY" "$AUDIT" --roster-root "$FIXTURE" --usage "$FIXTURE/wrong-shape.json" \
      --today "$TODAY" --json 2>&1)"; then
  if grep -q "Traceback" <<<"$out"; then fail "wrong-shaped usage file produced a traceback"
  else pass "wrong-shaped usage file degrades gracefully"; fi
else fail "wrong-shaped usage file crashed the run"; fi

# 8i. a usage key matching one unit's exact id is not also credited to another
#     unit that merely shares the bare name.
if [[ "$(field_of "used-skill" "uses")" == "15" && \
      "$(field_of "namesake@testmarket" "uses")" == "0" ]]; then
  pass "exact-id usage match is not double-credited to a bare-name namesake"
else fail "namesake plugin wrongly credited (used-skill=$(field_of "used-skill" "uses"), namesake=$(field_of "namesake@testmarket" "uses"))"; fi

# 8j. a skill and a command of the same name inside one plugin share an id;
#     the unit must count that usage once, not once per entry.
if [[ "$(field_of "twins@testmarket" "uses")" == "10" ]]; then
  pass "colliding ids inside one unit count usage once"
else fail "expected twins uses=10, got $(field_of "twins@testmarket" "uses")"; fi

# 8k. an unclosed frontmatter fence must not silently zero the description
if "$PY" "$AUDIT" --roster-root "$FIXTURE" --today "$TODAY" --json 2>&1 >/dev/null \
     | grep -q "unclosed frontmatter"; then
  pass "unclosed frontmatter fence warns on stderr"
else fail "unclosed frontmatter fence was silent"; fi

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
