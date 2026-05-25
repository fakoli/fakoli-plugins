# Critic Gate — Wave 4 Review

**Scope:**
- `plugins/cli-to-plugin/tests/smoke/test-gh-generation.sh`
- `plugins/cli-to-plugin/README.md`

**Cross-reference files read:**
- `docs/plans/2026-05-24-cli-to-plugin.md` (Tasks 9, 10)
- `docs/specs/2026-05-24-cli-to-plugin.md`
- `docs/plans/agent-task9-status.md`
- `docs/plans/agent-task10-status.md`
- `plugins/cli-to-plugin/commands/cli-to-plugin.md` (playbook)
- `plugins/cli-to-plugin/tests/fixtures/gh-help-tree.expected.json`

**Reviewed by:** critic
**Date:** 2026-05-25

---

## MUST FIX

None.

---

## SHOULD FIX

### 1. `test-gh-generation.sh` — "Unknown command" SKIP can mask a real execution failure

**File:** `plugins/cli-to-plugin/tests/smoke/test-gh-generation.sh:121`

The script fires the "Unknown command" SKIP check on any substring match, not anchored to the `/cli-to-plugin` command name:

```bash
if echo "$claude_output" | grep -q "Unknown command"; then
    echo "[smoke] SKIP: claude -p does not support slash commands ..."
    exit 0
fi
```

The `grep -q "Unknown command"` pattern is unanchored. If `claude` is installed and slash commands do work, but the playbook itself calls `find` or another tool that fails with output containing the words "Unknown command" (e.g., a shell error message from a misconfigured environment), the smoke test would SKIP and exit 0 rather than exposing the real failure. The same is true if some future version of `claude` changes its error text to "Unknown command '/cli-to-plugin': not installed" — which would still match — but now that message means "plugin not installed" rather than "slash commands unsupported", and the distinction matters for CI diagnostics.

The fix is to anchor the check to the specific command path, and optionally check that `claude_exit` was still 0 (since a proper slash-command failure would likely exit non-zero):

```bash
if echo "$claude_output" | grep -qF "Unknown command: /cli-to-plugin"; then
    echo "[smoke] SKIP: /cli-to-plugin slash command not available in this claude -p environment"
    echo "[smoke] (claude output: $claude_output)"
    exit 0
fi
```

Using `-F` (fixed string) prevents the pattern from matching via regex accident, and anchoring to `/cli-to-plugin` ensures only the relevant command triggers SKIP.

---

### 2. `test-gh-generation.sh` — mktemp failure detection checks the wrong variable

**File:** `plugins/cli-to-plugin/tests/smoke/test-gh-generation.sh:81-86`

```bash
TMP="$(mktemp -d /tmp/cli-to-plugin-smoke-XXXX)"
mkdir_result=$?
if [ $mkdir_result -ne 0 ] || [ ! -d "$TMP" ]; then
```

The variable is called `mkdir_result` but the operation is `mktemp`. This is a naming confusion that will mislead the next maintainer reading a failure message ("could not create temp directory") into thinking `mkdir` was the call that failed. The code is functionally correct but the name is wrong.

```bash
TMP="$(mktemp -d /tmp/cli-to-plugin-smoke-XXXX)"
mktemp_result=$?
if [ $mktemp_result -ne 0 ] || [ ! -d "$TMP" ]; then
    echo "[smoke] FAIL: could not create temp directory" >&2
    exit 1
fi
```

---

## CONSIDER

### 3. `test-gh-generation.sh` — Plan spec (Task 9) required `claude --no-interactive`; script uses `claude -p`

**File:** `plugins/cli-to-plugin/tests/smoke/test-gh-generation.sh:116`

The plan (Task 9, acceptance criteria) states:

> Uses `claude --no-interactive` with `/cli-to-plugin gh --from-tree ...`

The script uses `claude -p "$SLASH_COMMAND"` instead. The agent-task9-status.md documents this decision: `--no-interactive` does not exist in the installed version; `-p`/`--print` is the actual non-interactive flag.

This is a valid deviation given the runtime environment. The decision is documented in both the script header and the status file. No action required — surfaced here for the audit trail. If the installed `claude` CLI is ever upgraded and gains a `--no-interactive` flag with different semantics, the smoke test should be revisited.

---

### 4. `test-gh-generation.sh` — Groups are hard-coded; mismatch with fixture is a future hazard

**File:** `plugins/cli-to-plugin/tests/smoke/test-gh-generation.sh:34`

```bash
EXPECTED_GROUPS=(pr issue repo workflow release gist)
```

The fixture (`gh-help-tree.expected.json`) has exactly these 6 groups in this order. The hard-coding is correct and intentional for a smoke test. However, if the fixture is ever extended (e.g., adding `codespace` or `run` groups), the hard-coded list will silently under-assert — the test will pass without checking the new groups.

A stronger assertion would derive the group list from the fixture via `jq`:

```bash
mapfile -t EXPECTED_GROUPS < <(jq -r '.groups[].name' "$FIXTURE")
```

This is a consider, not a SHOULD FIX, because the fixture is a committed file under version control and any change to it should prompt a corresponding update to the smoke test. The current approach is safe for v1.

---

### 5. `README.md` — `--max-depth` and `--max-commands` are in README but not in the playbook's Argument parsing section

**File:** `plugins/cli-to-plugin/README.md:83-84`
**Cross-reference:** `plugins/cli-to-plugin/commands/cli-to-plugin.md:17-25`

The README documents:

```
| `--max-depth <n>`    | 3   | Maximum recursion depth when walking subcommand help trees |
| `--max-commands <n>` | 500 | Halt discovery with a warning if command count exceeds this |
```

The playbook's "Argument parsing" section does NOT list `--max-depth` or `--max-commands`. They appear only in the error handling table at the bottom of the playbook (as `Recursion depth > 3` and `Total commands walked > 500 → suggest --max-commands`).

As a result, if a user invokes `/cli-to-plugin gh --max-depth 2`, the playbook's first instruction is:

> "Treat unrecognised flags as an error: halt and print usage."

This means the playbook would halt on `--max-depth` even though the README documents it as a supported flag. This is a user-visible inconsistency: the README promises a feature the playbook actively rejects.

There are two fixes:

**Option A (minimal):** Add `--max-depth` and `--max-commands` to the playbook's Argument parsing section and thread them into Step 2 (pass to `discover.py`).

**Option B (conservative, for v1):** Remove `--max-depth` and `--max-commands` from the README's flags table and add a note in the Limitations section: "Discovery bounds (max depth, max command count) are controlled via the defaults in `discover.py`; override via `--override` is not yet supported."

Option A is the right fix long-term and aligns the README with what the spec describes as a supported parameter (`discover.py --max-depth`, `discover.py --max-commands`). Option B is acceptable if Wave 5 is needed before those flags are wired through.

This is a CONSIDER rather than MUST FIX only because the flags are pass-through to `discover.py` (not part of the interactive flow), and a user who hits the halt will see the usage message and understand they are not supported yet.

---

### 6. `README.md` — Quick start shows interactive output skeleton, but `--from-tree` is the non-interactive path

**File:** `plugins/cli-to-plugin/README.md:11-31`

The Quick Start section shows `/cli-to-plugin gh` and "Claude walks gh --help, discovers 12+ command groups, asks which ones to include..." This accurately describes the interactive happy path. However, the "Generated file tree for `gh`" skeleton shows meta-skills (`gh-review-and-merge`, `gh-cut-a-release`), which are only generated after the interactive meta-skill picker (Step 6). A new user reading this section will not realize the quick start requires two `AskUserQuestion` interactions before anything is written to disk.

A one-sentence callout would help:

> "Claude will ask two questions: which groups to include (all selected by default), and which workflow meta-skills to generate (none selected by default)."

This is a consider — the existing text is accurate but slightly incomplete for first-time users.

---

## NIT

### N1. `test-gh-generation.sh` — MARKETPLACE_ROOT path depth comment would help maintainability

**File:** `plugins/cli-to-plugin/tests/smoke/test-gh-generation.sh:27`

```bash
MARKETPLACE_ROOT="$SCRIPT_DIR/../../../.."
```

The agent-task9-status.md explains this is "4 levels up: smoke → tests → cli-to-plugin → plugins → root". A single inline comment in the script with this breadcrumb would make the path verifiable without needing to read the status file:

```bash
# smoke → tests → cli-to-plugin → plugins → marketplace-root
MARKETPLACE_ROOT="$SCRIPT_DIR/../../../.."
```

---

### N2. `README.md` — "Author" section is inconsistent with plugin convention

**File:** `plugins/cli-to-plugin/README.md:154-156`

```
## Author

Sekou Doumbouya — MIT License
```

The `nano-banana-pro` reference plugin (recommended by scout) does not have an Author section. The author and license are already declared in `plugin.json`. This section duplicates that information and adds potential drift (if the manifest author changes, the README author would need updating separately).

Consider removing the section and relying on the manifest + a "License: MIT" line in a "See also" section if needed.

---

### N3. `README.md` — Flags table alignment is uneven

**File:** `plugins/cli-to-plugin/README.md:75-84`

The table's `|---|---|---|` separator line has no column-width padding. This is stylistically consistent with the rest of this repository's tables, so this is a NIT rather than a real issue. Most markdown renderers handle it fine.

---

## Validation Status

`./scripts/validate.sh plugins/cli-to-plugin` exits 0 with exactly 2 WARNs:

- `WARN: Missing CHANGELOG.md`
- `WARN: license field set to 'MIT' but no LICENSE file found`

Both are expected and accepted — they are Wave 5 / release-gate items (marketplace sync via Task 12 covers LICENSE). No ERRORs. This matches the review brief's expectation of "2 WARN (CHANGELOG, LICENSE)".

`bash -n plugins/cli-to-plugin/tests/smoke/test-gh-generation.sh` exits 0 (clean syntax).

---

## Summary

### Smoke test (`test-gh-generation.sh`)

The script is structurally sound. It has no `set -e`, captures all exit codes explicitly, registers `trap cleanup EXIT` before the `mktemp` call, quotes all paths, and exits 0 on both SKIP paths. The two-tier SKIP design (no `claude` on PATH; `claude -p` silently prints "Unknown command") is well-reasoned and documented.

The primary weakness is the unanchored `grep -q "Unknown command"` check (SHOULD FIX #1), which could mask a real execution failure if anything else in the environment emits those words. Anchoring to `/cli-to-plugin` is a one-character fix.

The MARKETPLACE_ROOT path (4 levels up) is computed correctly and asserted before the temp dir is created, giving a clear diagnostic for runs in the wrong repo.

The hard-coded `EXPECTED_GROUPS=(pr issue repo workflow release gist)` matches the fixture exactly — confirmed by reading `gh-help-tree.expected.json` directly. All 6 groups are present in the fixture and in the array. The assertion logic (iterate over array, check for `$OUT/skills/gh-<group>/SKILL.md`, accumulate failures) is correct and would not produce a false pass.

If `claude -p` does work and executes the slash command, the assertion sequence is: plugin.json exists → parses as JSON → README.md exists → 6 skill SKILL.md files exist → validate.sh exits 0 → test-path-resolution.sh exits 0. This covers the spec's smoke requirements completely.

### Plugin README

The README meets all Task 10 acceptance criteria. It opens with a concrete value proposition in the first line, the Quick Start is copy-pasteable, prerequisites cover uv (with install command), target CLI, and jq. All 7 flags required by the plan are documented. The override YAML example covers all four override types (skip, description, extra_guidance, meta_skills). The Limitations section accurately reflects the spec's Out of Scope list. The spec is linked under "See also". No emojis. No "coming soon" sections.

The one genuine gap is CONSIDER #5: `--max-depth` and `--max-commands` are documented in the README but are not wired into the playbook's Argument parsing section. The playbook will halt on these flags as "unrecognised". This is a consistency issue between Wave 3 (playbook) and Wave 4 (README) that should be resolved before the plugin is marked release-ready.

---

Verdict: PASS

The two SHOULD FIX items are quality issues, not correctness blockers. The smoke test's core assertion logic is correct, the SKIP paths are sound, and the README accurately describes the plugin. The `--max-depth`/`--max-commands` inconsistency (CONSIDER #5) is a pre-release item that must be resolved before Wave 6 sign-off, but it does not block Wave 4 merge.
