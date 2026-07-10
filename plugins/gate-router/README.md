# gate-router

Deterministic **changed-path → verify-command** routing. The repo's own gates
("docs changed → docs strict build", "shell changed → `bash -n`", "src changed
→ run the suite") live in a per-project rules file, not in anyone's memory —
the retro-corpus finding this implements: recurring failures were
deterministic local checks nobody consistently ran.

## Rules file

`.claude/gate-router.local.md` (local settings pattern; typically git-ignored):

```markdown
---
rules:
  - docs/** => mkdocs build --strict
  - "**/*.sh" => bash -n {files}
  - bin/src/** => cd bin && uv run pytest -q
---
Notes for humans (ignored by the router).
```

`**` crosses directories; leading `**/` also matches root-level paths;
`{files}` expands to the matched files; duplicate commands run once, in rule
order.

## Use

```bash
scripts/gate-router.sh --list          # what the current changes require
scripts/gate-router.sh --run           # run gates, stop on first failure
scripts/gate-router.sh --list --json   # machine-readable
scripts/gate-router.sh --base main     # explicit diff base (default origin/main)
```

The changed set is committed-vs-base + staged + unstaged + **untracked** —
the full "about to ship" surface. In Claude Code: `/gate-check`; composes
with `ship-loop` step 4. Works identically on Windows (Git Bash) and Linux;
Codex runs the same script via the skill.

## License

MIT
