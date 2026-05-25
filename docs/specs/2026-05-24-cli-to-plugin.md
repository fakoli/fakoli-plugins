# cli-to-plugin — Spec

**Date:** 2026-05-24
**Status:** Draft (pending user approval)
**Author:** Sekou Doumbouya
**Canonical example:** `gh` (GitHub CLI)

---

## Goal

Build a Claude Code plugin (`cli-to-plugin`) that converts any well-behaved CLI into a self-contained Claude Code plugin made up of:

1. One **skill per top-level command group** (e.g., `gh-pr`, `gh-issue`, `gh-repo`) — gives Claude reliable trigger descriptions and a focused command reference.
2. A user-curated set of **meta-skills** that encode multi-command workflows (e.g., "review and merge PRs", "cut a release"). Proposed by Claude from the discovered help tree; the user picks which to generate via a multi-select.

The output is a plugin that lives independently of the generator — pure markdown, no runtime dependencies on `cli-to-plugin` itself.

## Context

This marketplace exists to curate Claude Code plugins. Today, each plugin is hand-authored. A non-trivial fraction of valuable plugins would just be "Claude knows how to use `<some CLI>` well" — `gh`, `kubectl`, `docker`, `aws`, `gcloud`, `terraform`, etc.

Hand-authoring such plugins is repetitive: walk the CLI's `--help` output, organize by group, write trigger descriptions, document command flags. Most of this is mechanical. The interesting part — workflow design — comes once.

`cli-to-plugin` automates the mechanical 80% and asks the user to curate the interesting 20%.

## Architectural decisions

1. **Skill-driven, not command-mirroring.** The generated plugin contains skills that *teach Claude when and how to call the CLI*, not one slash command per subcommand. Claude executes the CLI via Bash; the skill is the guidance. This avoids hundreds of generated command files and leverages Claude's reasoning.

2. **Hybrid discovery.** Default: recursively walk `<cli> --help`. Optional: a user-supplied `overrides.yaml` for renaming groups, skipping noise, supplying intent guidance, or pre-specifying meta-skills.

3. **One skill per top-level command group.** Better trigger descriptions than one skill per CLI, less file proliferation than one skill per leaf command.

4. **LLM-proposed meta-skills, user-picked.** After per-group skills are written, Claude reads the help tree it just gathered and proposes 5–10 workflow meta-skills. User picks via `AskUserQuestion` multi-select (with free-form additions).

5. **Plugin + scripts, no external CLI surface.** The utility runs entirely inside Claude Code as `/cli-to-plugin <name>`. No standalone executable. Internal Python scripts where determinism matters (help-tree parsing); Claude does everything else (synthesis, proposal, file writes).

6. **Python via `uv run --script` with PEP 723 metadata.** Scripts self-declare Python version + deps. No virtualenv ceremony.

## Components

```
plugins/cli-to-plugin/
├── .claude-plugin/plugin.json
├── commands/
│   └── cli-to-plugin.md            # the playbook Claude follows
├── scripts/
│   ├── discover.py                 # walks `<cli> --help` recursively → JSON tree
│   └── validate-output.sh          # runs marketplace validators on generated plugin
├── templates/
│   ├── group-skill.md              # structural reference for per-group skills
│   ├── meta-skill.md               # structural reference for workflow skills
│   └── plugin.json.example         # manifest reference
├── tests/
│   ├── test_discover.py
│   ├── test_override_merge.py
│   ├── fixtures/                   # captured --help trees for gh, kubectl, docker
│   └── smoke/test-gh-generation.sh
└── README.md
```

### Generated plugin layout (example: `gh`)

```
gh/
├── .claude-plugin/plugin.json
├── skills/
│   ├── gh-pr/SKILL.md              # per-group
│   ├── gh-issue/SKILL.md
│   ├── gh-repo/SKILL.md
│   ├── gh-workflow/SKILL.md
│   ├── ...
│   ├── gh-review-and-merge/SKILL.md  # meta-skill, user-picked
│   └── gh-cut-a-release/SKILL.md     # meta-skill
└── README.md
```

The generated plugin has **no runtime dependency** on `cli-to-plugin` — it's pure markdown.

## Data model

### Help tree (output of `discover.py`)

```json
{
  "cli": {
    "name": "gh",
    "binary": "/usr/local/bin/gh",
    "version": "2.40.0",
    "summary": "Work seamlessly with GitHub from the command line.",
    "homepage": "https://cli.github.com"
  },
  "global_flags": [
    {"short": "-R", "long": "--repo", "argument": "OWNER/REPO", "description": "..."}
  ],
  "groups": [
    {
      "name": "pr",
      "path": ["pr"],
      "summary": "Manage pull requests",
      "commands": [
        {
          "name": "list",
          "path": ["pr", "list"],
          "summary": "List pull requests",
          "usage": "gh pr list [flags]",
          "flags": [
            {"short": "-s", "long": "--state", "argument": "string", "description": "open|closed|merged|all"}
          ]
        }
      ]
    }
  ],
  "discovery": {
    "depth_reached": 2,
    "commands_walked": 47,
    "elapsed_ms": 1820,
    "warnings": []
  }
}
```

**Schema file:** `plugins/cli-to-plugin/schemas/help-tree.schema.json` — canonical contract, used by tests and downstream synthesis.

Each command's `path` array (`["pr", "list"]`) lets Claude reconstruct the exact invocation without name-parsing.

### Per-group SKILL.md

```yaml
---
name: gh-pr
description: Use when working with GitHub pull requests — listing, viewing, creating, reviewing, merging, or commenting on PRs via the `gh` CLI.
---
```

Body sections (markdown):
- **When to use** — concrete trigger scenarios + "do NOT use for X" boundary clauses
- **Commands** — table: subcommand | purpose | example
- **Common patterns** — 2–3 canonical recipes
- **Reference** — pointer to `<cli> <group> --help` for full flags

Description style is locked to **"Use when..."** + concrete intents — this is what Claude scans to decide triggering.

### Meta-skill SKILL.md (workflow)

```yaml
---
name: gh-review-and-merge
description: Use when the user wants to review pending pull requests assigned to them and merge approved ones. Multi-step workflow using the `gh` CLI.
---
```

Body sections:
- **When to use** — intent description
- **Workflow** — numbered steps with exact commands
- **Variants** — common modifications
- **Related** — `[[name]]` links to per-group skills

### Generated `plugin.json`

```json
{
  "name": "gh",
  "version": "1.0.0",
  "description": "Use the `gh` CLI through Claude — pull requests, issues, repos, workflows, and releases.",
  "author": {"name": "<from git config>"},
  "license": "MIT",
  "keywords": ["gh", "github", "cli", "generated", "cli-to-plugin"]
}
```

The `"cli-to-plugin"` keyword lets later tooling find all generated plugins for bulk operations.

### Override file (optional, `overrides.yaml`)

```yaml
plugin:
  name: gh
  author: {name: "Sekou Doumbouya"}

groups:
  - name: alias
    skip: true                      # do not generate a skill for this group

  - name: pr
    description: "..."              # override LLM-written trigger description
    extra_guidance: |               # appended to skill body
      Default to --state open unless the user specifies otherwise.

meta_skills:
  # If present, skips the LLM proposal step entirely
  - name: gh-cut-a-release
    description: "..."
    steps:
      - "gh release list"
      - "gh workflow run release.yml --ref main"
      - "gh release create v$VERSION --generate-notes"
```

All keys optional. With no override file, Claude infers everything from the help tree.

## Data flow

### Happy path

```
/cli-to-plugin gh --out ./plugins/gh
  ├─ Step 1: Preflight (which uv, which gh)
  ├─ Step 2: uv run --script discover.py gh > /tmp/tree.json
  ├─ Step 3: Confirm scope (Claude shows groups; AskUserQuestion multi-select)
  ├─ Step 4: Write per-group skills (Write tool, atomic via .tmp + rename)
  ├─ Step 5: Propose 5–10 meta-skills (Claude reads tree, synthesizes)
  ├─ Step 6: User picks (AskUserQuestion multi-select + free-form)
  ├─ Step 7: Write meta-skills (Write tool, atomic)
  ├─ Step 8: Write plugin.json + README.md
  ├─ Step 9: validate-output.sh (validate.sh + test-path-resolution.sh)
  └─ Step 10: Summary block (groups generated, meta-skills, validation status, warnings)
```

### Regeneration

When `--out` directory exists and is non-empty, ask each time:

- **A. Overwrite all generated files** — hand-edits lost
- **B. Diff-and-merge** (recommended) — regenerate to a temp dir, walk file pairs, show diffs, accept/reject per file, apply accepted changes
- **C. Cancel**

Recommended workflow for users with customizations: keep them in `overrides.yaml`, not in the generated SKILL.md files. The override file is re-read every run.

### Override file integration

- **Step 2:** `groups[].skip` filters tree before downstream steps see it.
- **Step 4:** `groups[].description` used verbatim. `groups[].extra_guidance` appended to skill body.
- **Step 5:** If `meta_skills` present, skip LLM proposal entirely; use user-supplied workflows.

### `--from-tree <path>` escape hatch

Skips Step 2 entirely; loads a previously captured help tree from disk. Used for:
- Resuming after a discovery hiccup
- CI smoke tests (no live CLI needed)
- Iterating on synthesis logic with a stable input

Ship in v1.

## Error handling

Three severity levels:

| Severity | Meaning | User action |
|---|---|---|
| **Halt** | Cannot proceed | Fix and re-run |
| **Warn** | One artifact affected | Review, optionally fix |
| **Info** | Worth noting | Acknowledged in summary |

### Preflight (Halt)
- `uv` not on PATH → install command shown
- Target CLI not on PATH
- `--override` file missing or malformed YAML

### Discovery
- Root help non-zero AND stdout empty → **Halt**
- Root help non-zero but stdout has content → **Warn**, parse anyway
- Sub-help timeout (>5s) → **Warn**, skip subtree
- Sub-help unparseable → **Warn**, capture raw text in tree node as `raw_help`
- Recursion depth > 3 → **Info**, stop recursing
- Total commands walked > 500 → **Warn**, suggest `--max-commands`

ANSI codes stripped pre-parse. Force `LANG=C.UTF-8`. UTF-8 decode with `errors="replace"`.

### Synthesis
- SKILL.md fails `schemas/skill.schema.json` → **Warn**, retry once with schema error in re-prompt; keep file with flag if still failing
- `plugin.json` fails `schemas/plugin.schema.json` → **Halt** after one retry
- File write fails → **Halt**, clean up `.tmp` files
- Override references unknown group → **Halt** (typo protection, with suggestion)
- Override references unknown command in known group → **Warn**

Atomic writes: write to `<path>.tmp`, rename into place. A halt mid-synthesis leaves only the files that completed successfully.

### Validation
- `validate.sh` ERROR → **Halt**, display findings inline
- `validate.sh` WARN → **Info**, listed in summary
- `test-path-resolution.sh` ERROR → **Halt**

### User cancellation
- Cancel at scope confirmation → exit clean
- Cancel at meta-skill picker → per-group skills already written; offer "keep partial?"
- Ctrl+C → atomic-write invariant means disk is consistent; orphan `.tmp` files cleaned on next run

### Summary block (always shown)

```
Plugin: ./plugins/gh
─────────────────────────────────────
Groups generated      : 12 ✓
Meta-skills generated : 4  ✓
Validation            : PASS (2 warnings)
─────────────────────────────────────
Warnings:
  - gh-alias: command list partially parsed (--help format atypical)
  - validate.sh: missing LICENSE file (recommended)

Next steps:
  - Try the plugin: /plugin install ./plugins/gh
  - Customize: edit overrides.yaml and re-run with --regen
```

## Testing

### Unit + fixtures (`discover.py`)

- Located at `plugins/cli-to-plugin/tests/test_discover.py`
- Fixtures: real captured `--help` output for `gh`, `kubectl`, `docker`, plus pathological cases (ANSI, non-zero exit, deep recursion, empty stdout, 5s timeout)
- Run: `uv run --with pytest pytest plugins/cli-to-plugin/tests/`
- Coverage gate: 90% on `discover.py`

### Schema validation

Every generated SKILL.md and `plugin.json` validates against existing marketplace schemas. Runs inside the playbook (Step 9) AND in CI as a gate.

### End-to-end smoke (via `--from-tree`)

`tests/smoke/test-gh-generation.sh` — feeds `gh` fixture tree to the playbook, asserts:
- All expected files exist
- Every group in fixture has a corresponding skill
- `validate.sh` and `test-path-resolution.sh` pass on output

Headless via `claude --no-interactive` + a `--no-meta-skills` playbook flag (skips the interactive AskUserQuestion steps).

### Manual smoke matrix (release gate)

Interactive runs against three CLIs with different help styles:
- `gh` (indented blocks, deep groups)
- `kubectl` (tabular, high command count)
- `docker` (section headers, mixed flags/commands)

Install the generated plugin, exercise per-group and meta-skill triggers in a fresh Claude Code session. Human-judged. Required before tagging a release.

### CI integration

`.github/workflows/cli-to-plugin-tests.yml`:
- Trigger: PRs touching `plugins/cli-to-plugin/**`
- Runs: pytest, smoke script, `validate.sh` on the plugin itself
- Existing marketplace-wide validation continues to run on `plugins/**`

## Acceptance criteria

A v1 release is shippable when all of these are true:

1. `discover.py` correctly parses `gh`, `kubectl`, and `docker` help trees against committed expected JSON.
2. `/cli-to-plugin gh` produces a plugin that passes `./scripts/validate.sh` and `./scripts/test-path-resolution.sh`.
3. Every generated SKILL.md validates against `schemas/skill.schema.json`. Every generated `plugin.json` validates against `schemas/plugin.schema.json`.
4. Override file with `skip`, `description`, `extra_guidance`, and pre-specified `meta_skills` are all honored end-to-end.
5. Regeneration into an existing directory asks the user (overwrite / diff-and-merge / cancel) and behaves correctly for each choice.
6. `--from-tree <path>` skips discovery and feeds the loaded tree into synthesis.
7. `uv` preflight halts cleanly with an install hint when `uv` is missing.
8. The generated `gh` plugin works in a fresh Claude Code session: invoking `gh-pr` triggers correctly; at least one meta-skill (e.g., `gh-review-and-merge`) walks through its workflow.
9. `discover.py` pytest coverage ≥ 90%.
10. Manual smoke matrix (gh, kubectl, docker) passes.

## Out of scope (v1)

- Generating slash commands or agents (only skills).
- Auto-update detection when the CLI version bumps server-side.
- Headless meta-skill selection — relies on interactive `AskUserQuestion`. CI uses `--no-meta-skills` to skip.
- Wrapping CLIs without `--help` support — assume a POSIX-ish CLI emits help on `--help`.
- Plugin distribution / pushing to the marketplace — manual `git add`, PR, merge.
- Multi-language CLI binaries (e.g., wrapping a CLI whose subcommands shell out to language-specific tools with their own help formats).
- Resumable interactive sessions — Ctrl+C requires a re-run; we don't persist progress across runs.

## Open questions resolved during brainstorm

| Question | Decision |
|---|---|
| Plugin shape (command-mirror vs. skill-driven vs. agent vs. hybrid) | **Skill-driven (B)** |
| Discovery mechanism | **Hybrid: `--help` parsing + optional YAML override (D)** |
| Skill granularity | **One skill per top-level command group (B)** |
| Meta-skill proposal | **LLM-proposed, user-picked via multi-select (A)** |
| Packaging surface | **Plugin only, no external CLI; internal scripts where determinism helps** |
| Python execution | **`uv run --script` with PEP 723 inline metadata** |
| Regeneration default | **Ask each time; diff-and-merge is the recommended choice** |
| `--from-tree` in v1 | **Yes** |
| Synthesis retry budget | **1 retry, then warn (or halt for `plugin.json`)** |
| Override mismatch handling | **Group typo → halt with suggestion; command typo → warn** |
