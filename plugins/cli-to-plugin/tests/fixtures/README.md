# Test Fixtures

This directory contains raw captured CLI help outputs and hand-curated expected JSON trees used by `discover.py` tests (Wave 3).

---

## Test Strategy

### Raw fixtures are partial captures, not full CLI mirrors

The raw fixture directories (`gh-help-raw/`, `kubectl-help-raw/`, `docker-help-raw/`) cover a **representative subset** of each CLI's help surface — they do NOT capture every command. For example, `gh-help-raw/` contains 7 files covering the root plus 6 groups; the real `gh` CLI has 31+ top-level commands.

### How Wave 3 tests use fixtures (monkeypatch strategy)

Wave 3 tests use a `monkeypatch_subprocess` fixture that intercepts `subprocess.run` calls and returns:
- The corresponding raw fixture file content for **known invocations** (e.g., `gh pr --help` → `gh-pr.txt`)
- Empty stdout with exit code 0 for **unknown invocations** (e.g., `gh auth --help` → no fixture)

`discover.py` treats empty stdout as "no subcommands" — a valid leaf command response. Commands not covered by fixtures appear as bare group entries with no `commands[]`.

### How expected fixtures are structured (subset matching)

Each `*-help-tree.expected.json` describes the **subset of groups** that `discover.py` MUST correctly produce when given the raw fixture files as input. They are NOT a full snapshot of running against the live binary.

Wave 3 tests compare using **subset assertion on groups**:

```python
actual = {g["name"]: g for g in discovered["groups"]}
expected = {g["name"]: g for g in expected_tree["groups"]}
for name, exp_group in expected.items():
    assert name in actual, f"expected group {name!r} not in output"
    # deep-compare the curated group only
    assert actual[name] == exp_group
```

Extra groups in actual output (representing commands not in the raw fixture set) are allowed. The test passes as long as every group in the expected fixture appears in the actual output.

### Command entries do not include usage or flags

Expected JSON command entries (inside `groups[].commands[]`) contain only `name`, `path`, and `summary`. They do NOT include `usage` or `flags` — those fields require depth-3 raw fixture captures (e.g., `gh-pr-list.txt`) which are out of scope for this fixture set. Discovery tests assert on `name`, `path`, and `summary` only at the command level.

### global_flags reflects root --help FLAGS section only

`global_flags` in the expected fixtures reflects **only what appears in the root `--help`'s FLAGS section**. INHERITED FLAGS shown in sub-command help outputs are NOT extracted into `global_flags`. For `gh`, the root FLAGS section contains only `--help` and `--version`; the other flags (`--repo`, `--jq`, `--json`, `--template`, `--web`) appear in INHERITED FLAGS sections of sub-help outputs and are not global from `discover.py`'s perspective.

### Flatten convention for deep groups

Deep command paths are promoted to **top-level sibling entries** in `groups[]`. Nesting is expressed via `path` length, not nested objects. For example, `kubectl create deployment` would appear as:

```json
{"name": "create-deployment", "path": ["create", "deployment"], "commands": [...]}
```

as a sibling of `{"name": "create", "path": ["create"], ...}`, not as a child of `create`. Since the raw fixtures do not include `kubectl create deployment --help`, the `create-deployment` flat group does not appear in the kubectl expected fixture — it would only appear when running against the live binary.

---

## Structure

```
tests/fixtures/
├── gh-help-raw/              Raw --help captures from the gh CLI (GitHub CLI)
├── kubectl-help-raw/         Raw --help captures from kubectl (Kubernetes CLI)
├── docker-help-raw/          Raw --help captures from docker CLI
├── gh-help-tree.expected.json      Hand-curated expected discover.py output for gh (subset)
├── kubectl-help-tree.expected.json Hand-curated expected discover.py output for kubectl (subset)
├── docker-help-tree.expected.json  Hand-curated expected discover.py output for docker (subset)
└── pathological/             Edge-case inputs that exercise error handling
```

---

## Real CLI Fixtures

### `gh-help-raw/`

**Provenance:** Captured live from `gh` version 2.92.0 at `/opt/homebrew/bin/gh` on macOS Darwin 25.5.0 (2026-05-24).

| File | Command | Purpose |
|------|---------|---------|
| `gh.txt` | `gh --help` | Top-level help; lists all command groups |
| `gh-pr.txt` | `gh pr --help` | Pull request group; ~15 subcommands |
| `gh-issue.txt` | `gh issue --help` | Issue group; ~12 subcommands |
| `gh-repo.txt` | `gh repo --help` | Repository group; ~14 subcommands |
| `gh-workflow.txt` | `gh workflow --help` | GitHub Actions workflow group; 5 subcommands |
| `gh-release.txt` | `gh release --help` | Release management group; ~9 subcommands |
| `gh-gist.txt` | `gh gist --help` | Gist management group; 7 subcommands |

**Tests using this fixture:**
- `test_discover.py::test_real_gh_fixture_matches_expected` — drives `discover.py` with monkeypatched subprocess returning these files, then uses subset assertion against `gh-help-tree.expected.json`.

### `kubectl-help-raw/`

**Provenance:** Captured live from `kubectl` v1.34.1 at `/usr/local/bin/kubectl` on macOS Darwin 25.5.0 (2026-05-24).

| File | Command | Purpose |
|------|---------|---------|
| `kubectl.txt` | `kubectl --help` | Top-level help; all command categories |
| `kubectl-get.txt` | `kubectl get --help` | Resource display command (no subcommands) |
| `kubectl-create.txt` | `kubectl create --help` | Resource creation command + subcommand listing |
| `kubectl-apply.txt` | `kubectl apply --help` | Configuration application command + subcommands |
| `kubectl-describe.txt` | `kubectl describe --help` | Resource description command (no subcommands) |

**Tests using this fixture:**
- `test_discover.py::test_kubectl_fixture_validates_against_schema`

**Note:** kubectl uses Mixed-Case section headings with colons (`Available Commands:`, `Options:`, `Basic Commands (Beginner):`). The section detector handles these correctly.

### `docker-help-raw/`

**Provenance:** Captured live from `docker` version 29.3.1 at `/usr/local/bin/docker` on macOS Darwin 25.5.0 (2026-05-24).

| File | Command | Purpose |
|------|---------|---------|
| `docker.txt` | `docker --help` | Top-level help; management commands + common commands |
| `docker-container.txt` | `docker container --help` | Container lifecycle management |
| `docker-image.txt` | `docker image --help` | Image management |
| `docker-volume.txt` | `docker volume --help` | Volume management |
| `docker-network.txt` | `docker network --help` | Network management |

**Tests using this fixture:**
- `test_discover.py::test_docker_fixture_validates_against_schema`

**Note:** docker uses Mixed-Case section headings with colons (`Common Commands:`, `Management Commands:`, `Commands:`, `Global Options:`). The section detector handles these correctly.

---

## Expected JSON Trees

Each `*.expected.json` file is a hand-curated **subset** of what `discover.py` should produce from the corresponding raw fixtures. They validate against `schemas/help-tree.schema.json`.

### `gh-help-tree.expected.json`
- Covers 6 groups: `pr`, `issue`, `repo`, `workflow`, `release`, `gist`
- 2–5 representative commands per group as bare entries (`name`, `path`, `summary` only — no `usage` or `flags`)
- `global_flags`: only `--help` and `--version` (from root FLAGS section)
- `discovery.depth_reached: 2`, `commands_walked: 28`
- The remaining 25+ groups from `gh --help` are not in this fixture but will appear in actual discover.py output

### `kubectl-help-tree.expected.json`
- Covers 2 representative groups: `create` (with bare leaf commands), `apply` (with bare leaf commands)
- Commands appear as bare entries with only `name`, `path`, `summary` — no flags — because no depth-3 fixtures exist for kubectl subcommands
- `get` and `describe` groups are not in the expected fixture (they have no subcommands in the fixture set)
- Nesting convention demonstrated: deep groups like `create-deployment` would appear as top-level siblings in actual output against the live binary

### `docker-help-tree.expected.json`
- Covers 4 groups: `container`, `image`, `volume`, `network`
- Commands appear as bare entries with `name`, `path`, `summary` only (no `usage` or `flags`)
- `global_flags` contains all 11 flags from Docker's root `Global Options:` section

---

## Pathological Fixtures

Located in `pathological/`. Each file exercises a specific failure mode in `discover.py`.

### `ansi-codes.txt`
**Tests:** ANSI escape sequence stripping before parsing.

A fake `--help` output containing ANSI color and style codes (`\x1b[1m`, `\x1b[31m`, `\x1b[0m`, etc.). `discover.py` must strip all ANSI sequences before attempting to parse the help text. After stripping, the output should parse identically to a plain-text equivalent.

Expected behavior: `discover.py` strips sequences, produces a valid help tree, no warnings.

### `exits-nonzero.txt`
**Tests:** Non-zero CLI exit code with non-empty stdout.

Represents stdout from a CLI that prints full help text but exits with code 1 on `--help`. Per spec, `discover.py` must:
- Parse the stdout anyway (not abort)
- Add a warning entry about the non-zero exit
- Continue the discovery walk

Expected behavior: discovery completes, `discovery.warnings` contains one entry about the non-zero exit.

### `empty-stdout.txt`
**Tests:** CLI that prints nothing on `--help`.

An empty file (0 bytes). Represents a CLI that outputs nothing when `--help` is passed. `discover.py` must:
- Detect empty stdout
- Exit non-zero with a clear error message to stderr
- NOT emit a partial JSON tree to stdout

Expected behavior: subprocess call returns empty string; discover.py raises a fatal error.

### `deep-foo.txt`, `deep-foo-bar.txt`, `deep-foo-bar-baz.txt`, `deep-foo-bar-baz-qux.txt`
**Tests:** Recursion depth limit enforcement.

Four separate files representing each level of a 5-level synthetic command tree (`foo bar baz qux quux`). Split into separate files so monkeypatched tests can return different content per invocation depth level.

Monkeypath mapping:
- `foo --help` → `deep-foo.txt` (depth 0)
- `foo bar --help` → `deep-foo-bar.txt` (depth 1)
- `foo bar baz --help` → `deep-foo-bar-baz.txt` (depth 2)
- `foo bar baz qux --help` → `deep-foo-bar-baz-qux.txt` (depth 3 — at limit)
- `foo bar baz qux quux --help` → NOT called (depth 4 exceeds limit)

Expected behavior: discovery stops at depth 3, depth-4 commands appear as bare leaves, `discovery.warnings` contains "depth limit reached" or similar entries.

**Note:** The original `deep-recursion.txt` (single file with all levels concatenated) is kept for historical reference but should not be used directly as a monkeypatch source.

### `timeout.sh`
**Tests:** Per-call subprocess timeout.

An executable bash script that sleeps 6 seconds before printing any output. The default per-call timeout in `discover.py` is 5 seconds. When wired into tests, this script must cause `discover.py` to:
- Kill the subprocess after 5 seconds
- Log a warning about the timeout
- Skip that command and continue (not abort the whole walk)

The script is intentionally 1 second longer than the default timeout to allow for CI timing variance. Make executable with `chmod +x`.

Expected behavior: subprocess is terminated; discovery continues; `discovery.warnings` contains a timeout warning.

---

## Schema Validation

All `*.expected.json` files are validated against `schemas/help-tree.schema.json` in CI and can be checked locally:

```bash
uv run --with jsonschema python -c "
import json, jsonschema
schema = json.load(open('plugins/cli-to-plugin/schemas/help-tree.schema.json'))
for f in [
    'plugins/cli-to-plugin/tests/fixtures/gh-help-tree.expected.json',
    'plugins/cli-to-plugin/tests/fixtures/kubectl-help-tree.expected.json',
    'plugins/cli-to-plugin/tests/fixtures/docker-help-tree.expected.json',
]:
    jsonschema.validate(json.load(open(f)), schema)
    print(f'PASS: {f}')
"
```

## Size Limits

No fixture exceeds 100KB. Raw capture files are typically 1–5KB. Expected JSON files are 5–20KB.
