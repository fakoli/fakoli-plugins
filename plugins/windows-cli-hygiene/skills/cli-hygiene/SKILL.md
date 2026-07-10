---
name: cli-hygiene
description: Scan source for Windows/cross-platform CLI hazards before shipping — non-ASCII in printed strings (the cp1252 console crash), hardcoded python3, heredoc backslash mangling, Node .cmd/.bat spawns, set -e in hooks. Use when the user asks to "check for encoding issues", "scan for Windows portability", "cli hygiene", is about to ship a CLI/script change, or wants the deterministic form of the ship-loop Windows discipline. Advisory (never blocks); wire it as a gate-router gate.
user-invocable: true
---

# CLI Hygiene

Deterministic scan for the Windows/cross-platform CLI hazards the retro corpus
kept re-discovering by hand — the scanner form of ship-loop's "Windows/platform
discipline" (step 3).

## Scan

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/scan-cli-hygiene.sh"            # scan .
bash "${CLAUDE_PLUGIN_ROOT}/scripts/scan-cli-hygiene.sh" src bin   # scan paths
bash "${CLAUDE_PLUGIN_ROOT}/scripts/scan-cli-hygiene.sh" --json
```

Output is `file:line: RULE message`; the scan is **advisory and always exits
0** — a wrapper (gate-router, CI) decides whether a finding blocks. Report the
findings to the user and offer to fix them.

## What it flags

| Rule | Hazard | Fix |
|---|---|---|
| `NON_ASCII_OUTPUT` | non-ASCII byte in a string headed to stdout (em-dash, arrow, ✎) | crashes a cp1252 Windows console with `UnicodeEncodeError` — use ASCII, or `sys.stdout.reconfigure(encoding="utf-8")` at entry |
| `PYTHON3_HARDCODE` | literal `python3` | often a broken WindowsApps alias; resolve `python3`→`python`, run tooling with `PYTHONUTF8=1` |
| `HEREDOC_BACKSLASH` | `\n`/`\t` inside a bash heredoc | mangled across the shell boundary — write a patch file and run it, or use `printf` |
| `CMD_SPAWN` | spawning `.cmd`/`.bat` from Node | `EINVAL` (CVE-2024-27980) unless shelled; resolve the real binary and spawn that |
| `SET_E_HOOK` | `set -e` in a `hooks/` script | a probe's non-zero exit would abort the hook; use `set -uo pipefail` |

## Precision

Advisory line-based heuristics, tuned to under- rather than over-report:
- Single-line matching — a `print`/`spawn` split across lines isn't seen.
- `PYTHON3_HARDCODE` matches the literal `python3` anywhere on a line (a
  comment or an error-message string counts). Treat findings as prompts to
  look, not as failures.
- CRLF is handled (a trailing carriage return is stripped before matching).

## Composition

- `ship-loop` step 3/4: run before the review gate.
- As a **gate-router** rule — the "CLI changed -> encoding smoke test" gate it
  advertises:
  ```
  - "**/*.py" => bash <path>/scan-cli-hygiene.sh {files}
  ```
- Runs on Windows (Git Bash) and Linux; Codex invokes the same script.
