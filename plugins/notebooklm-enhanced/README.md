# NotebookLM Enhanced

Operate NotebookLM notebooks, sources, grounded queries, research, and generated artifacts from Codex or Claude Code. This package uses [notebooklm-py](https://github.com/teng-lin/notebooklm-py), an **unofficial** client for undocumented Google RPCs. Google-side changes, account limits, and session expiration can affect operations.

## Setup

Install through the repository marketplace for your runtime. Requirements: Python 3.10+, `uv`, and a Google account with NotebookLM access. The bundled `scripts/uv.lock` pins `notebooklm-py` 0.8.2. Initial dependency setup may download packages.

Resolve the installed plugin root, then run its wrapper:

```bash
bash "/path/to/notebooklm-enhanced/scripts/notebooklm.sh" --version
bash "/path/to/notebooklm-enhanced/scripts/notebooklm.sh" auth check --json
```

Authentication check reports session readiness; `status` only shows local context. If sign-in is needed, inspect `login --help` and let the user complete the browser sign-in. This client stores browser session cookies; it is not a Google OAuth application. Browser setup may require the dependencies described in the upstream installation guide. Never print cookie files or `NOTEBOOKLM_AUTH_JSON`.

## Workflows

Codex receives `notebooklm-core` and `notebooklm-research` skills. Claude also receives seven commands (`setup`, `create-notebook`, `add-source`, `query`, `generate`, `library`, `research`) and a research agent. The skills preserve these capabilities without requiring command migration.

The wrapper resolves the package's own lockfile while preserving the caller's directory. Select full IDs from actual CLI responses and pass `--notebook` on each scoped operation. Automated workflows do not use the shared `use` context. Read the relevant `--help` before using an unfamiliar command; this avoids copied option tables drifting from the locked CLI.

For queries, continue with an explicit returned conversation ID when appropriate. In version 0.8.2, `ask --new` deletes the notebook's server-side conversation, and `--json` bypasses its confirmation. Use that option only for a requested history deletion, never as a generic fresh-query flag.

Create/upload/generate only within the requested workflow. Submission is not completion: retain the returned source, research-run, and artifact IDs; poll that operation with bounded calls and verify its state before downloading. `artifact wait` accepts `--timeout` and `--interval`. `research wait --import-all` has separate research and indexing timeout budgets, so use short budgets or separate status calls to keep each wait bounded. Inspect state before retrying an uncertain submission.

Download the selected ready artifact with an explicit output path and `--no-clobber` where supported. Return the verified file and source citations. A synthesis request does not automatically create a notebook, change global language settings, share data, or generate extra artifacts.

## Verification

From the repository root:

```bash
python3 -m unittest discover -s plugins/notebooklm-enhanced/tests -p 'test_*.py' -v
```

Tests use a fake `uv` to verify installation paths and argument preservation, then run the locked CLI's help commands under a temporary NotebookLM home. They never authenticate, query notebooks, or contact the NotebookLM API. Package downloads may occur on first use. Live account integration is not covered by these tests.

The upgrade and command contracts were checked against [upstream documentation](https://github.com/teng-lin/notebooklm-py) and the locked 0.8.2 CLI help on 2026-09-05.

MIT licensed.
