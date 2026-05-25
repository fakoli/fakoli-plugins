# Task 4 Status — Capture test fixtures from real CLIs

**Status:** COMPLETE
**Date:** 2026-05-24
**Agent:** scout

---

## Verify Results

```
all fixtures valid      ← schema validation of all 3 expected JSON files
size limit OK           ← no fixture exceeds 100KB (macOS wc -l has leading spaces; actual count is 0)
```

Note on the size-check verify command: `wc -l | grep -q '^0$'` fails on macOS because `wc -l` pads output with spaces (e.g., `       0`). The actual file count is 0. All fixtures are under 20KB.

---

## Acceptance Criteria Checklist

- [x] `tests/fixtures/gh-help-raw/` — 7 files: `gh.txt` + 6 group captures (`pr`, `issue`, `repo`, `workflow`, `release`, `gist`)
- [x] `tests/fixtures/gh-help-tree.expected.json` — 6 groups, 2–5 commands per group, 7 global flags, validates against schema
- [x] `tests/fixtures/kubectl-help-raw/` — 5 files: `kubectl.txt` + `get`, `create`, `apply`, `describe`
- [x] `tests/fixtures/kubectl-help-tree.expected.json` — 5 groups (including depth-2 `create-deployment`), validates against schema
- [x] `tests/fixtures/docker-help-raw/` — 5 files: `docker.txt` + `container`, `image`, `volume`, `network`
- [x] `tests/fixtures/docker-help-tree.expected.json` — 4 groups, 3–4 commands per group, validates against schema
- [x] `tests/fixtures/pathological/ansi-codes.txt` — contains 37 real ANSI ESC bytes (`\x1b[...m`)
- [x] `tests/fixtures/pathological/exits-nonzero.txt` — documented exit behavior in header comments
- [x] `tests/fixtures/pathological/empty-stdout.txt` — 0 bytes (truly empty)
- [x] `tests/fixtures/pathological/deep-recursion.txt` — 5-level synthetic tree (`foo bar baz qux quux`)
- [x] `tests/fixtures/pathological/timeout.sh` — sleeps 6s (1s longer than default 5s timeout), executable
- [x] `tests/fixtures/README.md` — documents all fixtures, provenance, and purpose
- [x] No fixture exceeds 100KB (largest is `gh-help-tree.expected.json` at 17KB)

---

## Provenance

- **gh:** Live capture from `/opt/homebrew/bin/gh` version 2.92.0 on macOS Darwin 25.5.0
- **kubectl:** Live capture from `/usr/local/bin/kubectl` v1.34.1 on macOS Darwin 25.5.0
- **docker:** Live capture from `/usr/local/bin/docker` version 29.3.1 on macOS Darwin 25.5.0

All three CLIs were installed and available. No docs-sourced help text was used.

---

## Schema Notes

The `kubectl-help-tree.expected.json` demonstrates the flat-groups convention:
- `create-deployment` appears as a top-level group with `path: ["create", "deployment"]` — a sibling of `create`, not nested inside it
- Commands within `get` and `describe` groups use resource type names as command names (e.g., `path: ["get", "pods"]`) since kubectl takes resource types as positional arguments rather than named subcommands
- All command `path` arrays have `minItems: 2` as required by the schema

---

## Files Modified

- `plugins/cli-to-plugin/tests/fixtures/gh-help-raw/gh.txt` (created)
- `plugins/cli-to-plugin/tests/fixtures/gh-help-raw/gh-pr.txt` (created)
- `plugins/cli-to-plugin/tests/fixtures/gh-help-raw/gh-issue.txt` (created)
- `plugins/cli-to-plugin/tests/fixtures/gh-help-raw/gh-repo.txt` (created)
- `plugins/cli-to-plugin/tests/fixtures/gh-help-raw/gh-workflow.txt` (created)
- `plugins/cli-to-plugin/tests/fixtures/gh-help-raw/gh-release.txt` (created)
- `plugins/cli-to-plugin/tests/fixtures/gh-help-raw/gh-gist.txt` (created)
- `plugins/cli-to-plugin/tests/fixtures/gh-help-tree.expected.json` (created)
- `plugins/cli-to-plugin/tests/fixtures/kubectl-help-raw/kubectl.txt` (created)
- `plugins/cli-to-plugin/tests/fixtures/kubectl-help-raw/kubectl-get.txt` (created)
- `plugins/cli-to-plugin/tests/fixtures/kubectl-help-raw/kubectl-create.txt` (created)
- `plugins/cli-to-plugin/tests/fixtures/kubectl-help-raw/kubectl-apply.txt` (created)
- `plugins/cli-to-plugin/tests/fixtures/kubectl-help-raw/kubectl-describe.txt` (created)
- `plugins/cli-to-plugin/tests/fixtures/kubectl-help-tree.expected.json` (created)
- `plugins/cli-to-plugin/tests/fixtures/docker-help-raw/docker.txt` (created)
- `plugins/cli-to-plugin/tests/fixtures/docker-help-raw/docker-container.txt` (created)
- `plugins/cli-to-plugin/tests/fixtures/docker-help-raw/docker-image.txt` (created)
- `plugins/cli-to-plugin/tests/fixtures/docker-help-raw/docker-volume.txt` (created)
- `plugins/cli-to-plugin/tests/fixtures/docker-help-raw/docker-network.txt` (created)
- `plugins/cli-to-plugin/tests/fixtures/docker-help-tree.expected.json` (created)
- `plugins/cli-to-plugin/tests/fixtures/pathological/ansi-codes.txt` (created)
- `plugins/cli-to-plugin/tests/fixtures/pathological/exits-nonzero.txt` (created)
- `plugins/cli-to-plugin/tests/fixtures/pathological/empty-stdout.txt` (created)
- `plugins/cli-to-plugin/tests/fixtures/pathological/deep-recursion.txt` (created)
- `plugins/cli-to-plugin/tests/fixtures/pathological/timeout.sh` (created, chmod +x)
- `plugins/cli-to-plugin/tests/fixtures/README.md` (created)
- `docs/plans/agent-task4-status.md` (this file)
