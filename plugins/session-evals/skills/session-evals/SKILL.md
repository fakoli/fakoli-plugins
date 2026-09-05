---
name: session-evals
description: Mine past coding-agent sessions (Claude Code, Codex, OpenClaw, Cursor CLI) into local-model eval suites executable via anvil-serving. Retro-first — consumes session-retro output dirs and cross-session findings themes, curates candidates into deterministic check-based evals sized for local models, emits anvil-serving-compatible eval-data suites, and runs them against any OpenAI-compatible endpoint. Use when the user asks to "create evals from my sessions", "build local-model evals", "turn this retro into evals", "which work classes can my local model handle", or wants evidence for anvil-serving routing decisions. Reads only local session logs; writes only to the eval-data root the user chooses.
---

Resolve `PLUGIN_ROOT` from the host-provided `PLUGIN_ROOT` / `CLAUDE_PLUGIN_ROOT`, or from this loaded skill’s directory (`../..`). Use that absolute path for the bundled commands; do not assume the current directory is the install root.


# Session Evals

Turn real sessions into the evals that decide what your local models are
trusted to do. The scripts do the deterministic work; **your job is
curation** — choosing candidates, writing checks, redacting, sizing.

## Toolkit (bundled, stdlib-only)

```bash
M="${PLUGIN_ROOT}/scripts/session_miner.py"
E="${PLUGIN_ROOT}/scripts/eval_emit.py"
python3 "$M" list [substr]                      # browse sessions, all sources
python3 "$M" mine --corpus <findings-dir> --out cands.json   # retro-first
python3 "$M" mine --retro <retro-dir>  --out cands.json      # one retro
python3 "$M" mine <session.jsonl ...>  --out cands.json      # raw sessions
python3 "$E" emit <spec.json>                   # -> ~/.anvil-serving/eval-data/
python3 "$E" run  <suite-dir> --base-url http://127.0.0.1:30001/v1 --model <m>
```

## Steps

1. **Start from the retro corpus when one exists** (default:
   `~/post-session-findings` or a project's `post-session-findings/`).
   `mine --corpus` reads `cross_session_findings.json` (severity-ranked
   failure themes) and every retro's `session_stats.json` (exact source
   session paths) — the error analysis is already done; don't redo it.
   Fall back to `mine --retro <dir>` for one retro, or raw session paths
   (find them with `list` / session-retro's `find`).

2. **Curate candidates into a spec.** Read the mined candidates (ranked:
   tool calls with structured args, human-correction followups, diffs,
   local-fit context first). For each eval you keep:
   - Write **deterministic checks** — `contains` / `contains_all` /
     `contains_any` on the response, and/or `expect_tool` (name +
     required args) when the candidate was a tool call. The captured
     cloud action is *inspiration, not ground truth* — checks must state
     what a correct answer contains, not "matches what Claude did".
   - **Redact** anything flagged in `redaction_flags` plus names, private
     paths, and URLs the eval doesn't need. The eval text will outlive
     the session.
   - Assign the **work_class** (anvil-serving taxonomy, one per suite) and
     a **context_bucket** (8192/16384/32768) — compact the prompt to fit;
     record the bucket, it is a difficulty dimension.
   - Tag `provenance` (theme id, session path, turn_ts) so every eval
     traces back: theme -> session -> turn -> eval -> profile row.
   Group evals into one spec per work class (spec shape: header of
   `eval_emit.py`). 5-15 evals per suite is plenty; prefer several small
   themed suites over one grab-bag.

3. **Review the curated batch** for correct checks, scope, and redactions. If the user requested creating local evals, emit the reviewable files directly. Local emission needs no extra confirmation.

4. **Emit.** `eval_emit.py emit spec.json` writes
   `~/.anvil-serving/eval-data/<date>-<work_class>-<suite>/` (suite.json,
   prompts/, provenance.json). It refuses to overwrite unless `--force`.

5. **Run against the requested endpoint and model** when running is in scope. Do not start services or send session content to an unspecified endpoint. After redaction, use
   `eval_emit.py run <suite-dir> --base-url ... --model ... --out
   evidence.json`. Exit 0 = all passed, 2 = some failed. Report the
   pass rate per work class and what it suggests for the quality profile
   (allow / allow-with-verify / deny). Repeat per tier/model as asked.

## Notes

- **Privacy:** mining reads local logs; running sends curated prompts and tool definitions to the selected endpoint. Redaction flags are indicators, not automatic removal or a completeness guarantee. Mining reads only local logs (`~/.claude`, `~/.codex`,
  `~/.cursor`, OpenClaw via `\\wsl$`); writes only candidates/spec/
  evidence files locally. Session text must be redacted at curation time.
- **OpenClaw:** sessions live inside its WSL distro
  (`\\wsl$\<distro>\home\<user>\.openclaw\agents\*\agent\codex-home\sessions`);
  override roots with `SESSION_EVALS_OPENCLAW_ROOTS` if autodiscovery
  misses. Only the embedded-codex rollout store is supported today.
- **Formats drift.** Parsers are tolerant; if a source yields zero
  candidates from a session you know has tool calls, flag it — don't
  shrug (the schema probably moved).
- Existing candidate/evidence files require `--overwrite`; existing suites require `--force`. Use distinct output paths from the input sessions/spec.
- See [README](../../README.md) for the spec schema, check semantics, and the
  anvil-serving integration story (`--suite-file` upstream plan).
