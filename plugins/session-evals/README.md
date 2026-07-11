# session-evals

Mine your real coding-agent sessions into eval suites for **local models**,
executable via [anvil-serving](https://github.com/fakoli/anvil-serving).

Public benchmarks measure the wrong distribution. Your sessions *are* your
workload: this plugin turns them into per-work-class evidence for the
question anvil-serving routes on — *is this local model trusted for this
kind of work?*

## Use it

```
/session-evals            # or: "create evals from my sessions"
```

The skill walks: mine -> curate -> emit -> run.

## How it works

```
cross_session_findings.json (failure themes, severity-ranked)
        |
retro dirs (session_stats.json -> exact session paths + human turns)
        |
session_miner.py  -> ranked eval candidates (JSON)
        |
curation (Claude + you: checks, redaction, work class, context bucket)
        |
eval_emit.py emit -> ~/.anvil-serving/eval-data/<date>-<work_class>-<suite>/
        |
eval_emit.py run  -> evidence JSON (pass rate per suite/model)
```

Provenance is unbroken: theme -> session -> turn -> eval -> profile row.

### Session sources

| Source | Location | Format |
|--------|----------|--------|
| Claude Code | `~/.claude/projects/**/*.jsonl` | Anthropic content blocks |
| Codex CLI | `~/.codex/sessions/**/*.jsonl` + `~/.codex/archived_sessions/` (cold rollouts move there) | rollout (`type`+`payload`) |
| OpenClaw | `\\wsl$\<distro>\home\<u>\.openclaw\agents\*\agent\codex-home\sessions\**` | codex rollout (embedded agent) |
| Cursor CLI | `~/.cursor/projects/*/agent-transcripts/*/*.jsonl` | role/message blocks |

Set `SESSION_EVALS_OPENCLAW_ROOTS` (path-separator-separated dirs) when
OpenClaw autodiscovery misses. Not yet supported: Cursor's GUI history
(`state.vscdb` SQLite — undocumented, update-fragile) and OpenClaw's
native tree-structured session store; both are candidates for a later
version.

### Spec and check semantics

A curated spec is one suite per work class; full schema in the header of
[`scripts/eval_emit.py`](scripts/eval_emit.py). Checks are deterministic
and mirror anvil-serving's benchmark engine exactly:

- `contains` / `contains_all` / `contains_any` — lowercased substring
  checks on the response text (`evaluate_text_checks`).
- `expect_tool` — the response's first tool call must name the expected
  function, parse as JSON, and carry the required args
  (`validate_function_tool_call`). Requires a `tools` array.

No LLM-as-judge: small local models are unreliable graders, and the run
must be reproducible offline.

### Why deterministic checks against *curated* expectations

The captured cloud action is not automatically correct — sessions record
what happened, including mistakes. Curation writes checks for what a
correct answer contains; the session supplies the task, the context, and
the difficulty, not the answer key.

### anvil-serving integration

- Suites land in `~/.anvil-serving/eval-data/` next to your
  `serves.toml`, named `<date>-<work_class>-<suite>` so the work class is
  machine-readable from the dir name (same convention its profile
  bootstrap uses).
- `eval_emit.py run` speaks to any OpenAI-compatible endpoint (a serve
  directly, or the router) with `temperature 0`, and writes evidence JSON
  with a `failures` list, in the spirit of anvil-serving's bakeoff
  artifacts.
- Planned upstream: `anvil-serving eval benchmark run --suite-file` so
  suites run inside its evidence pipeline natively. Until then the
  bundled runner covers execution; the suite format is already
  compatible.

Suggested reading of results: high pass rate at 32k -> candidate `allow`;
passes only with tool checks relaxed -> `allow-with-verify`; structural
failures -> `deny`. Promotion into a quality profile stays a human call.

## Privacy

- Reads only local session logs; sends nothing anywhere.
- Mined candidates carry `redaction_flags` (key/token patterns); the
  skill's curation step requires redaction before emit.
- Evals default to `~/.anvil-serving/eval-data/` — outside any repo — so
  session-derived text is not accidentally committed or published.

## Tests

```bash
uv run --with pytest pytest plugins/session-evals/tests/ -q
```

## License

MIT — see [LICENSE](LICENSE).
