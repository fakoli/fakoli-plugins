# Changelog

All notable changes to the gate-router plugin. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - 2026-07-09

### Added

- `scripts/gate-router.sh` routes the changed set (committed vs base + staged
  + unstaged + untracked) through per-project `glob => command` rules in
  `.claude/gate-router.local.md`; `--list`, `--run` (stop on first failure,
  propagate rc), `--json`.
- `gate-check` skill + `/gate-check` command; `config/gate-router.example.md`
  starter rules file.
- Segment-aware globbing (single `*` stays within a path segment; `**`
  crosses); matched files passed as argv (injection-safe filenames);
  `--list` renders `{files}` shell-quoted (copy-paste-safe).
- No bash-4 features (regex globbing + parallel indexed arrays), so it runs
  on Windows (Git Bash), Linux, and macOS bash 3.2. 21-assertion sandboxed
  test suite; executed on Linux in CI.
