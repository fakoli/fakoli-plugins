# Changelog

## 1.1.0 — 2026-09-05

- Correct heredoc expansion and combined-errexit checks, handle arbitrary filenames through JSON, report input errors, and add an optional --fail-on-findings gate.
- Added native Codex discovery alongside the existing Claude entrypoints and focused offline regressions.

All notable changes to the windows-cli-hygiene plugin. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.1] - 2026-08-08

### Fixed

- `PYTHON3_HARDCODE` no longer fires on a `#!/usr/bin/env python3` shebang.
  A shebang is correct on POSIX and never consulted on Windows (scripts run
  as `python foo.py`); only an inline `python3` invocation hits the broken
  WindowsApps alias. Regression test added for both directions.

## [1.0.0] - 2026-07-09

### Added

- `scripts/scan-cli-hygiene.sh` — advisory scanner for five Windows/cross-
  platform CLI hazards (NON_ASCII_OUTPUT, PYTHON3_HARDCODE, HEREDOC_BACKSLASH,
  CMD_SPAWN, SET_E_HOOK); `file:line: RULE msg` text or `--json`, always
  exit 0. `cli-hygiene` skill + `/cli-hygiene` command. 19-assertion suite;
  Windows (Git Bash) + Linux; no bash-4 features. Heredoc detection is a
  proper delimiter-tracking state machine (handles quoted/digit delimiters
  and `<<-` tab-indented closers); a trailing CR is stripped so CRLF
  checkouts don't misread as non-ASCII; the scanner excludes itself even
  when passed as an explicit argument.
