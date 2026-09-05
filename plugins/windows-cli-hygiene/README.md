# windows-cli-hygiene

Scan CLI source for portability risks. Native Codex skills and Claude commands are included. Python 3.10+ is required; the Bash compatibility wrapper resolves `python3` or `python`.

```bash
python scripts/scan_cli_hygiene.py [PATH ...] --json
bash scripts/scan-cli-hygiene.sh [PATH ...] --fail-on-findings
```

No paths means the current directory. Findings are advisory by default (exit 0). `--fail-on-findings` returns 1 when hazards are found; missing/unreadable inputs return 2. Arbitrary filenames are preserved in JSON output.

| Rule | What to inspect |
|---|---|
| `NON_ASCII_OUTPUT` | Check the actual console or redirected encoding; non-ASCII does not always fail in legacy codepages. |
| `PYTHON3_HARDCODE` | Use `sys.executable` for Python children, or resolve an available interpreter. |
| `UNQUOTED_HEREDOC` | Shell expressions expand unless the delimiter is quoted; quote it when literal data is intended. |
| `CMD_SPAWN` | Batch files need an interpreter; prefer real executables and preserve argument boundaries. |
| `SET_E_HOOK` | Bare, combined, and named `errexit` options can abort on expected failing probes. |

The former `HEREDOC_BACKSLASH` rule incorrectly treated literal `\n` and `\t` as broken. Those sequences are valid; the scanner now checks actual shell expansion. This is a line-based heuristic, not a language parser or a native Windows execution test. It skips comments and common generated directories.

```bash
bash tests/test-scan-cli-hygiene.sh
python -m unittest discover -s tests -p 'test_scanner_safety.py'
```

Shell behavior reference: [Bash redirections](https://www.gnu.org/s/bash/manual/html_node/Redirections.html). License: MIT.
