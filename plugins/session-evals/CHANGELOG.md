# Changelog

All notable changes to the session-evals plugin.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - 2026-07-11

### Added

- `session_miner.py` — stdlib-only candidate mining from four session
  sources (Claude Code, Codex, OpenClaw via WSL UNC, Cursor CLI
  agent-transcripts) with retro-first input modes (`--retro`, `--corpus`)
  that consume session-retro output and cross-session failure themes.
- `eval_emit.py` — spec validation, anvil-serving-compatible eval-data
  emission (`~/.anvil-serving/eval-data/<date>-<work_class>-<suite>/`),
  and a deterministic runner for any OpenAI-compatible endpoint
  (check semantics mirror anvil-serving's benchmark engine).
- `session-evals` skill — the mine -> curate -> emit -> run workflow with
  redaction and provenance requirements.
- pytest suite with synthetic fixtures for all three parser variants.
