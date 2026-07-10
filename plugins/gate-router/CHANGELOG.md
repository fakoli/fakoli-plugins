# Changelog

## 1.0.0

- Initial release: `scripts/gate-router.sh` routes the changed set (committed
  vs base + staged + unstaged + untracked) through per-project
  `glob => command` rules in `.claude/gate-router.local.md`; `--list`,
  `--run` (stop on first failure, propagate rc), `--json`. `gate-check`
  skill + `/gate-check` command. 13-assertion sandboxed test suite; runs on
  Windows (Git Bash) and Linux identically.
