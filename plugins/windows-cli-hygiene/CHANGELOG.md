# Changelog

All notable changes to the windows-cli-hygiene plugin. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - 2026-07-09

### Added

- `scripts/scan-cli-hygiene.sh` — advisory scanner for five Windows/cross-
  platform CLI hazards (NON_ASCII_OUTPUT, PYTHON3_HARDCODE, HEREDOC_BACKSLASH,
  CMD_SPAWN, SET_E_HOOK); `file:line: RULE msg` text or `--json`, always
  exit 0. `cli-hygiene` skill + `/cli-hygiene` command. 13-assertion suite;
  Windows (Git Bash) + Linux; no bash-4 features.
