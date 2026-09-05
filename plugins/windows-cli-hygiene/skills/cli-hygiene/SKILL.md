---
name: cli-hygiene
description: Scan CLI source for output-encoding risks, interpreter assumptions, unquoted heredoc expansion, Windows batch spawning, and hook errexit. Use for portability reviews or requested CLI hygiene checks.
---

# CLI Hygiene

Resolve `<plugin-root>` from the loaded skill (`../..`) or host plugin-root variable. The scanner needs Python 3.10+; its Bash wrapper chooses `python3` or `python`.

```bash
python "<plugin-root>/scripts/scan_cli_hygiene.py" [PATH ...] --json
bash "<plugin-root>/scripts/scan-cli-hygiene.sh" [PATH ...]
```

No paths means the current directory. Default findings are advisory (exit 0); `--fail-on-findings` returns 1 for findings. Unreadable/missing inputs return 2 and are not a clean scan. Report limits alongside findings.

- `NON_ASCII_OUTPUT`: check the actual console/redirected encoding; some non-ASCII characters are valid in legacy codepages.
- `PYTHON3_HARDCODE`: prefer `sys.executable` for Python children or explicitly resolve an installed interpreter.
- `UNQUOTED_HEREDOC`: shell expressions expand; quote the delimiter when literal data is intended. Literal `\n` and `\t` are not inherently broken.
- `CMD_SPAWN`: inspect how batch files launch and keep user data out of shell command strings.
- `SET_E_HOOK`: both `set -euo` and `set -o errexit` enable early exit. Handle expected probe failures explicitly.

These are line-based heuristics, not a full language parser or proof of Windows compatibility. Comments and common generated directories are skipped. Run targeted native tests when available; do not claim a Windows run from this scan alone. Apply fixes when already requested. See [README](../../README.md).
