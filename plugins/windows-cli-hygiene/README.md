# windows-cli-hygiene

Deterministic scan for the Windows/cross-platform CLI hazards the retro corpus
kept re-discovering by hand — the **scanner form of ship-loop's "Windows
discipline"**. Advisory (`exit 0`); wire it as a gate-router gate or a CI step.

## Hazards

| Rule | What | Fix |
|---|---|---|
| `NON_ASCII_OUTPUT` | non-ASCII in a stdout string (em-dash / arrow / ✎) | crashes cp1252 consoles — ASCII, or reconfigure stdout to UTF-8 |
| `PYTHON3_HARDCODE` | literal `python3` | broken WindowsApps alias risk; resolve python3→python + `PYTHONUTF8=1` |
| `HEREDOC_BACKSLASH` | `\n`/`\t` in a bash heredoc | mangled across the shell boundary; use a patch file / printf |
| `CMD_SPAWN` | `.cmd`/`.bat` spawn from Node | EINVAL (CVE-2024-27980) unless shelled |
| `SET_E_HOOK` | `set -e` in a `hooks/` script | aborts the hook on a non-zero probe |

## Use

```bash
scripts/scan-cli-hygiene.sh [path ...] [--json]   # default: .
```

`/cli-hygiene` in Claude Code; the same script runs under Codex and on Linux.
Composes with `gate-router` ("CLI changed → encoding smoke test") and
`ship-loop` step 3/4.

## License

MIT
