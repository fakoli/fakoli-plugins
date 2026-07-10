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
with `ship-loop` step 4.

## Trust & safety

The rules file **runs shell commands** — treat it like a Makefile and only
`--run` in repos you trust. Matched filenames are passed as **argv**, never
interpolated into the shell, so a changed file named `x;rm -rf ~.sh` is an
inert argument, not code — but the commands you write run with your
privileges. `{files}` paths are repo-root-relative; don't pair `{files}` with
a command that `cd`s elsewhere. Gitignore `.claude/gate-router.local.md` (or
commit it deliberately as a shared, reviewed gate policy).

## Platforms

Bash + git only; **no bash-4-only features** (regex globbing, indexed arrays),
so it runs on Windows (Git Bash), Linux, and macOS's system bash 3.2. Tested
in CI on Linux and locally on Windows.

## License

MIT
