---
name: gate-check
description: Route changed file paths to the verify commands this repo requires before shipping — docs changed means docs strict build, shell changed means bash -n, CLI changed means the encoding smoke test. Use before committing/opening a PR, when the user asks "what checks do I need to run", "run the gates", "gate check", or after substantive edits in a repo with a .claude/gate-router.local.md rules file. Deterministic local gates instead of session memory; also helps AUTHOR the rules file for a new repo.
user-invocable: true
---

# Gate Check

Deterministic changed-path → verify-command routing. The rules live in the
project, not in anyone's memory: `.claude/gate-router.local.md` (the
marketplace's plugin-settings pattern).

## Check the current diff

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/gate-router.sh" --list       # what's required
bash "${CLAUDE_PLUGIN_ROOT}/scripts/gate-router.sh" --run        # run them, stop on failure
bash "${CLAUDE_PLUGIN_ROOT}/scripts/gate-router.sh" --list --json
```

- Default diff base is `origin/main` (fall back `HEAD`); override with
  `--base <ref>`. The changed set is committed-vs-base + staged + unstaged —
  the full "about to ship" surface.
- `--run` executes gates in rule order and stops at the first failure with
  its exit code — report that failure to the user verbatim, fix, re-run.
- No config → the script says so and exits 0 (nothing to enforce). Suggest
  authoring one (below) when the repo clearly has gate-worthy surfaces.

## Author or extend the rules file

`.claude/gate-router.local.md`, rules in the frontmatter, `glob => command`:

```markdown
---
rules:
  - docs/** => mkdocs build --strict
  - "**/*.sh" => bash -n {files}
  - bin/src/** => cd bin && uv run pytest -q
  - plugins/** => bash scripts/validate.sh
---
Notes for humans below the fence (ignored by the router).
```

- `**` crosses directories; a leading `**/` also matches paths at the root.
- `{files}` expands to the matched files (space-separated) — use it for
  linters; omit it for suite commands.
- Duplicate commands from overlapping rules run once. Order = rule order.
- Derive rules from the repo's own history: CI workflow steps, CLAUDE.md
  test instructions, and past incident classes (encoding, docs links) are
  the gate candidates. Keep each gate FAST — these run per-change, not
  nightly.

## Composition

- `ship-loop` step 4 ("test against reality"): run `--run` before the review
  gate.
- Works identically on Windows (Git Bash) and Linux; Codex runs the same
  script via this skill (no hooks involved).
