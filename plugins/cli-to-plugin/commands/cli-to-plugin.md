---
description: Convert any CLI into a self-contained Claude Code skill-driven plugin
argument-hint: <cli-name> [--out path] [--override path] [--from-tree path] [--no-meta-skills] [--regen]
---

# cli-to-plugin

Convert a CLI tool into a Claude Code plugin by walking its `--help` tree, generating one
skill per command group, and (optionally) proposing workflow meta-skills for the user to
curate.

Full spec: `docs/specs/2026-05-24-cli-to-plugin.md`

## Argument parsing

Parse the invocation before doing anything else:

- `<cli-name>` — required; the binary to introspect (e.g., `gh`, `kubectl`)
- `--out <path>` — destination directory for the generated plugin; default: `./plugins/<cli-name>`
- `--override <path>` — YAML override file; optional
- `--from-tree <path>` — load a pre-captured help-tree JSON instead of running discovery
- `--no-meta-skills` — skip Steps 5, 6, and 7 entirely
- `--regen` — hint that regeneration is expected (triggers the regeneration flow automatically without prompting twice)
- `--max-depth <n>` — max recursion depth for `discover.py` (default `3`); forwarded as `--max-depth` to the script
- `--max-commands <n>` — halt discovery if the walked command count exceeds this (default `500`); forwarded as `--max-commands` to the script

Treat unrecognised flags as an error: halt and print usage.

---

## Pre-Step-0 — Override file validation

If `--override <path>` is set, verify the file exists and parses as YAML **before** running any other step. This runs regardless of `--from-tree`, so a broken override file fails fast.

```bash
test -f "$OVERRIDE_PATH" || { echo "HALT: override file not found: $OVERRIDE_PATH"; exit 1; }
uv run --with pyyaml -c "import yaml, sys; yaml.safe_load(open('$OVERRIDE_PATH'))"
```

On failure: **halt** with the parse error.

---

## Step 0 — Regeneration guard

Skip this step entirely when `--out` does not exist or is empty.

When `--out` exists and is non-empty:

- **If `--regen` was passed:** set `REGEN_MODE=diff-merge` automatically and skip the prompt. Proceed to Step 1.
- **If `--regen` was NOT passed:** ask the user:

```
AskUserQuestion: "Plugin already exists at <out>. How would you like to proceed?"

Options:
  A. Diff-and-merge (RECOMMENDED) — regenerate to a temp dir, walk file pairs, accept/reject per file
  B. Overwrite all — regenerate in place, hand-edits will be lost
  C. Cancel
```

- If the user picks **C**, exit cleanly.
- If the user picks **A**, set `REGEN_MODE=diff-merge`. Write all new files under `<out>/.regen-tmp/`, then at the end of Step 8 walk each pair and show a diff before applying.
- If the user picks **B**, set `REGEN_MODE=overwrite`. Proceed normally.

---

## Step 1 — Preflight

`uv` is required by every flow path (override merge, discovery, and validation all shell through it), so its check runs even when `--from-tree` is set. The `<cli-name>` check is skipped only when `--from-tree` is set, since no live CLI is needed.

```bash
command -v uv
[ -n "$FROM_TREE" ] || command -v <cli-name>
```

- If `uv` is not found: **halt** with this message:
  ```
  HALT: uv is not installed.
  Install it: curl -LsSf https://astral.sh/uv/install.sh | sh
  Then re-run this command.
  ```
- If `<cli-name>` is not found (and `--from-tree` was not passed): **halt** with:
  ```
  HALT: '<cli-name>' not found on PATH.
  Install it or pass --from-tree <path> to use a pre-captured tree.
  ```
Override file validation already ran in Pre-Step-0, so no override checks are needed here.

---

## Step 2 — Discover

Skip this step when `--from-tree <path>` is set.

Run discovery and capture the JSON tree:

```bash
uv run --script ${CLAUDE_PLUGIN_ROOT}/scripts/discover.py <cli-name> \
  ${MAX_DEPTH:+--max-depth $MAX_DEPTH} \
  ${MAX_COMMANDS:+--max-commands $MAX_COMMANDS} \
  > /tmp/cli-to-plugin-tree.json
```

Append `--max-depth` and `--max-commands` to the invocation only when the corresponding flag was passed by the user; otherwise rely on `discover.py`'s defaults (3 and 500 respectively).

If `--override <path>` is set, apply overrides to the tree immediately after discovery:

```bash
uv run --with pyyaml --script ${CLAUDE_PLUGIN_ROOT}/scripts/override.py \
  --tree /tmp/cli-to-plugin-tree.json \
  --override <override-path> \
  > /tmp/cli-to-plugin-tree-merged.json
mv /tmp/cli-to-plugin-tree-merged.json /tmp/cli-to-plugin-tree.json
```

If `--from-tree <path>` is set, copy the given path to `/tmp/cli-to-plugin-tree.json`:

```bash
cp "<from-tree-path>" /tmp/cli-to-plugin-tree.json
```

If `--override <path>` is also set alongside `--from-tree`, apply the override merge the same way.

Error handling:
- Root help exit non-zero AND stdout empty: **halt** with the stderr output.
- Root help exit non-zero but stdout has content: log `WARN: discover returned non-zero but produced output — parsing anyway`.
- Any sub-help timeout (>5s): logged as `WARN` in the discovery metadata; continue.

Read `/tmp/cli-to-plugin-tree.json` into memory. Note the `discovery.warnings` array — carry these into the final summary.

---

## Step 3 — Confirm scope

Read the `groups` array from the tree. Present it to the user and ask which groups to generate skills for:

```
AskUserQuestion: "Discovery found <N> command groups in <cli-name>. Which should I generate skills for?"

Options: (all groups pre-selected)
  [x] <group-name>  — <group-summary>
  ...

(Select all / Deselect all)
```

- Default: all groups selected.
- If the user deselects all: confirm intent before proceeding — this produces a plugin with no per-group skills.
- Record the selected groups as `SELECTED_GROUPS`.

If the user cancels at this prompt, exit cleanly with no files written.

---

## Step 4 — Write per-group skills

For each group in `SELECTED_GROUPS`:

1. Determine the skill name: join the group's `path` array with `-` and prepend the CLI name.
   - `["pr"]` → `gh-pr`
   - `["codespace", "ports"]` → `gh-codespace-ports`

2. Determine the output path:
   ```
   <out>/skills/<skill-name>/SKILL.md
   ```
   Create the directory with Bash if it does not exist:
   ```bash
   mkdir -p "<out>/skills/<skill-name>"
   ```

3. Read `${CLAUDE_PLUGIN_ROOT}/templates/group-skill.md` to understand the required structure.

4. Synthesize a SKILL.md from the group's `name`, `path`, `summary`, `commands`, and `flags`.
   - Use the template's section structure: frontmatter → When to use → Commands table → Common patterns → Reference.
   - Frontmatter `description` must follow the **"Use when..."** style (see template).
   - **Frontmatter keys must be hyphenated:** `user-invocable`, `argument-hint`, `allowed-tools`, `disable-model-invocation`. Do NOT use underscore forms — they fail `schemas/skill.schema.json` validation.
   - If an override `description` is set for this group, use it verbatim instead of synthesizing one.
   - If an override `extra_guidance` is set, append it as a new section at the end: `## Notes\n<extra_guidance>`.

5. Atomic write:
   - Use the Write tool to write to `<out>/skills/<skill-name>/SKILL.md.tmp`
   - Use Bash to rename: `mv "<out>/skills/<skill-name>/SKILL.md.tmp" "<out>/skills/<skill-name>/SKILL.md"`
   - If any error occurs before the `mv`, the `.tmp` file is orphaned but the original (if any) is untouched.

6. If `REGEN_MODE=diff-merge`, write to `<out>/.regen-tmp/skills/<skill-name>/SKILL.md` instead of the live path.

7. Log: `  Written: <out>/skills/<skill-name>/SKILL.md`

Continue to the next group. Do not halt on a single SKILL.md synthesis failure — log a `WARN` and continue.

---

## Step 5 — Propose meta-skills

Skip this step (and Steps 6–7) if `--no-meta-skills` is passed.

Read the full tree from `/tmp/cli-to-plugin-tree.json`. Synthesize 5–10 workflow meta-skill proposals.

Each proposal must include:
- `name` — kebab-case, prefixed with the CLI name (e.g., `gh-review-and-merge`)
- `description` — one sentence, "Use when..." style
- `commands` — list of concrete CLI invocations involved

If the override file contains a `meta_skills` list, skip synthesis entirely and use the override-supplied workflows as the proposals (present them to the user for confirmation, not generation).

Print the proposals in a numbered list before the multi-select question.

---

## Step 6 — User picks meta-skills

Skip if `--no-meta-skills` is passed.

Ask the user:

```
AskUserQuestion: "Which workflow meta-skills should I generate? (You can also type a new name to add a custom one.)"

Options:
  [ ] <meta-skill-name> — <description>
  ...
  [ ] + Add a custom workflow (type its name)
```

- Default: none selected (user must opt in).
- Free-form additions: if the user types a workflow name not in the list, synthesize it from scratch using the tree context.
- If the user cancels at this step: the per-group skills are already written. Offer:
  ```
  AskUserQuestion: "Meta-skill selection cancelled. Keep the per-group skills already written?"
  Options:
    A. Yes, keep them
    B. No, delete everything and exit
  ```

Record the selected meta-skills as `SELECTED_META_SKILLS`.

---

## Step 7 — Write meta-skills

Skip if `--no-meta-skills` is passed.

For each item in `SELECTED_META_SKILLS`:

1. Determine output path:
   ```
   <out>/skills/<meta-skill-name>/SKILL.md
   ```
   Create the directory:
   ```bash
   mkdir -p "<out>/skills/<meta-skill-name>"
   ```

2. Read `${CLAUDE_PLUGIN_ROOT}/templates/meta-skill.md` to understand the required structure.

3. Synthesize a SKILL.md with sections: frontmatter → When to use → Workflow (numbered steps with exact commands) → Variants → Related.
   - `Related` section should link to per-group skills using `[[skill-name]]` syntax.

4. Atomic write:
   - Write tool to `<out>/skills/<meta-skill-name>/SKILL.md.tmp`
   - Bash: `mv "<out>/skills/<meta-skill-name>/SKILL.md.tmp" "<out>/skills/<meta-skill-name>/SKILL.md"`

5. If `REGEN_MODE=diff-merge`, write to `<out>/.regen-tmp/` instead.

6. Log: `  Written: <out>/skills/<meta-skill-name>/SKILL.md`

---

## Step 8 — Write manifest and README

### 8a. Resolve author info

```bash
git config user.name
git config user.email
```

Use the output if available; fall back to `""` if git config is not set.

### 8b. Write plugin.json

Read `${CLAUDE_PLUGIN_ROOT}/templates/plugin.json.example` for structure.

Create `.claude-plugin/` if needed:
```bash
mkdir -p "<out>/.claude-plugin"
```

Synthesize the manifest from the tree's `cli` object:
- `name` — `cli.name`
- `version` — `"1.0.0"`
- `description` — `Use the '<cli-name>' CLI through Claude — <condensed cli.summary>.` (Strip any trailing punctuation from `cli.summary` before appending the period; some CLIs report summaries with a trailing period and a double period would be ugly.)
- `author.name` — from git config (or override `plugin.author.name`)
- `keywords` — `["<cli-name>", "cli", "generated", "cli-to-plugin"]`
- `license` — `"MIT"`

Atomic write:
- Write tool to `<out>/.claude-plugin/plugin.json.tmp`
- Bash: `mv "<out>/.claude-plugin/plugin.json.tmp" "<out>/.claude-plugin/plugin.json"`

If the resulting JSON fails `schemas/plugin.schema.json` validation, retry once with the schema error in the re-prompt. If it still fails: **halt**.

### 8c. Write README.md

Write a README with:
- Plugin name and description
- Installation: `/plugin install <out>`
- Skills table: one row per generated skill (per-group + meta)
- Regeneration note: "To update after a CLI upgrade, run `/cli-to-plugin <cli-name> --out <out> --regen`"
- Override hint: link to `docs/specs/2026-05-24-cli-to-plugin.md` override file section

Atomic write:
- Write tool to `<out>/README.md.tmp`
- Bash: `mv "<out>/README.md.tmp" "<out>/README.md"`

### 8d. Diff-and-merge resolution (if REGEN_MODE=diff-merge)

Walk each file under `<out>/.regen-tmp/`. For each file that differs from the live version:

```bash
diff "<out>/<relative-path>" "<out>/.regen-tmp/<relative-path>"
```

Show the diff and ask:

```
AskUserQuestion: "Apply this change to <relative-path>?"
Options:
  A. Yes, apply
  B. No, keep existing
```

After all files are walked, clean up the temp dir:
```bash
rm -rf "<out>/.regen-tmp"
```

---

## Step 9 — Validate

Run the marketplace validators on the output:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/validate-output.sh" "<out>"
```

Capture the exit code and full output.

- Exit 0: validation PASS. Count any `WARN` lines in the output for the summary.
- Exit non-zero: **halt**, display the validator output inline, and print:
  ```
  HALT: Validation failed. Fix the errors above and re-run with --regen.
  ```

Collect any `WARN` lines into `VALIDATION_WARNINGS`.

---

## Step 10 — Summary

Count:
- `N_GROUPS` — number of per-group skills written
- `N_META` — number of meta-skills written (0 if `--no-meta-skills`)
- `N_WARNINGS` — len(discovery warnings) + len(validation warnings)
- `VALIDATION_STATUS` — `PASS` or `FAIL`

Print the summary block exactly:

```
Plugin: <out>
─────────────────────────────────────
Groups generated      : <N_GROUPS> ✓
Meta-skills generated : <N_META>  ✓
Validation            : <VALIDATION_STATUS> (<N_WARNINGS> warnings)
─────────────────────────────────────
Warnings:
  - <each warning from discovery and validation, one per line>

Next steps:
  - Try the plugin: /plugin install <out>
  - Customize: edit overrides.yaml and re-run with --regen
```

If `--no-meta-skills` was passed, the meta-skills line reads:
```
Meta-skills generated : 0  (skipped via --no-meta-skills)
```

If there are no warnings, omit the Warnings section entirely.

---

## Error handling reference

| Condition | Severity | Action |
|---|---|---|
| `uv` not on PATH | Halt | Show install command |
| CLI not on PATH | Halt | Suggest `--from-tree` |
| `--override` file missing or malformed | Halt | Show parse error |
| Override references unknown group | Halt | Show group name + suggestion |
| Root help empty | Halt | Show stderr |
| Root help non-zero but has content | Warn | Parse anyway |
| Sub-help timeout | Warn | Skip subtree |
| Sub-help unparseable | Warn | Capture as `raw_help` |
| Override references unknown command | Warn | Log, continue |
| SKILL.md fails schema | Warn | Retry once; keep with flag if still failing |
| `plugin.json` fails schema | Halt | After one retry |
| File write fails | Halt | Clean up `.tmp` files |
| `validate.sh` ERROR | Halt | Display findings |
| `validate.sh` WARN | Info | Collected in summary |
| `test-path-resolution.sh` ERROR | Halt | Display findings |
| Recursion depth > 3 | Info | Stop recursing; no warning |
| Total commands walked > 500 | Warn | Suggest `--max-commands <N>` |

---

## Orphaned .tmp cleanup

At the start of any run, remove stale `.tmp` files from a previous interrupted run:

```bash
find "<out>" -name "*.tmp" -delete 2>/dev/null || true
```

Run this after argument parsing but before Step 0.

---

## Reference files

- Templates (read for structure, not substitution):
  - `${CLAUDE_PLUGIN_ROOT}/templates/group-skill.md`
  - `${CLAUDE_PLUGIN_ROOT}/templates/meta-skill.md`
  - `${CLAUDE_PLUGIN_ROOT}/templates/plugin.json.example`
- Scripts:
  - `${CLAUDE_PLUGIN_ROOT}/scripts/discover.py`
  - `${CLAUDE_PLUGIN_ROOT}/scripts/override.py`
  - `${CLAUDE_PLUGIN_ROOT}/scripts/validate-output.sh`
- Spec: `docs/specs/2026-05-24-cli-to-plugin.md`
