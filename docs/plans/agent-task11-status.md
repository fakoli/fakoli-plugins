# Task 11 — Add CI workflow for cli-to-plugin

**Agent:** keeper
**Date:** 2026-05-25
**Status:** DONE

## What was done

Created `.github/workflows/cli-to-plugin-tests.yml` — a focused GitHub Actions
workflow that runs pytest, the smoke test, and the marketplace validator against
`plugins/cli-to-plugin` on every PR or push touching that path.

## Acceptance criteria — verified

| Criterion | Result |
|---|---|
| File exists at `.github/workflows/cli-to-plugin-tests.yml` | PASS |
| Triggers on `pull_request` with `paths: ['plugins/cli-to-plugin/**']` | PASS |
| Triggers on `push` to `main` with same path filter | PASS |
| `astral-sh/setup-uv@v3` used to install uv | PASS |
| pytest run with `--cov-fail-under=90` coverage gate | PASS |
| Smoke script `tests/smoke/test-gh-generation.sh` invoked | PASS |
| `./scripts/validate.sh plugins/cli-to-plugin` invoked | PASS |
| `runs-on: ubuntu-latest` | PASS |
| Does not run repo-wide `validate.sh` (no bare `./scripts/validate.sh`) | PASS |
| YAML parses without error | PASS |

## Decisions

**uv action version pinned:** `astral-sh/setup-uv@v3` — matches the version
referenced in the task plan. Python pinned to `"3.11"` per the requirement that
`discover.py` needs `>=3.11`.

**Coverage report upload:** No upload step was added. The task acceptance criteria
require only a coverage gate (`--cov-fail-under=90`), not a report artifact. Adding
an upload step (e.g., Codecov or actions/upload-artifact) would extend scope beyond
what was specified. A comment was not added; this can be wired in a follow-up.

**jq placement:** The `Install jq` step is placed after pytest/smoke and before
the validate step that needs it. This keeps the Python environment setup together
at the top and avoids installing jq unnecessarily if pytest fails early.

**No repo-wide duplication:** The job calls `./scripts/validate.sh plugins/cli-to-plugin`
(single-plugin scope), not the bare `./scripts/validate.sh` (which scans all plugins
and already runs in `validate.yml` and `pr-check.yml`).

## Files changed

- `.github/workflows/cli-to-plugin-tests.yml` — created
