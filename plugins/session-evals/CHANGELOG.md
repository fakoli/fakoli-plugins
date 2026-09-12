# Changelog

## 1.2.0 — 2026-09-12

- Added an explicit Pi JSONL importer that follows the selected parent-linked
  leaf, pairs tool calls with results, and marks malformed, unknown, truncated,
  or incomplete records as partial rather than completion evidence.
- Added the bounded Pi event adapter and smoke runner for isolated
  fixture-scoped file edits, protected-oracle checks, strict completion/usage
  accounting, output limits, deadlines, and process-group cleanup.
- Added the three-task synthetic Pi comparison catalog (`scoped-edit`,
  `tool-serialization`, and `subprocess-boundary`). It proves runner and event
  boundaries only; it is not a full model-quality benchmark or live Pi/tool
  evaluation.

## 1.1.0 — 2026-09-05

- Validate malformed specifications and resource bounds before running, stage replacement suites before touching prior evidence, and protect candidate/evidence outputs with explicit replacement.
- Added native Codex discovery alongside the existing Claude entrypoints and focused offline regressions.

All notable changes to the session-evals plugin.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
