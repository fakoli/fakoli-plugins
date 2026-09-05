# Local creator upgrade — 2026-09-05

This directory contains a local improvement to the installed system skill. A future Codex update
may replace bundled system skills. Preserve a copy of this directory (excluding generated
`__pycache__`) in a user-owned versioned location before updating the host. This upgrade did not
install plugins, rewrite the real marketplace or global config, publish, or commit changes.

## Research basis

Official primary sources inspected on 2026-09-05:

- [OpenAI packaging and marketplace guide](https://developers.openai.com/plugins/build/plugins)
  (the previous `/codex/plugins/build` URL redirects here).
- [OpenAI skill UI metadata and invocation policy](https://learn.chatgpt.com/docs/build-skills).
- [OpenAI plugin use and fresh-session behavior](https://learn.chatgpt.com/docs/plugins).
- [Agent Skills specification](https://agentskills.io/specification).

Local read-only evidence: `codex-cli 0.153.4`; `codex plugin --help` exposes `add`, `list`,
`marketplace`, and `remove`; `codex plugin marketplace --help` exposes `add`, `list`, `upgrade`,
and `remove`. Its `list` description includes the marketplaces currently considered and their
roots. No actual marketplace mutation or plugin installation was used to test this upgrade.

The current landscape includes local and repository catalogs, a shared public plugin directory,
lifecycle hooks, registered connector mappings, bundled MCP servers, and portable Agent Skills.
Git and npm descriptors also exist; this scaffold deliberately maintains local entries without
converting those sources. Public submission and host-specific hook trust remain separate concerns.

## File and behavior inventory

| File | Previous behavior | Updated behavior |
| --- | --- | --- |
| `scripts/create_basic_plugin.py` | Always emitted `skills` even when absent; hardcoded source path; force replaced manifest/companions/entry | References only requested components; derives actual source path; default hooks file; array prompts; lossless extension; existing-plugin registration; preflight source/path/conflict checks |
| `scripts/validate_plugin.py` | Required catalog metadata for every plugin; rejected hooks; fixed companion paths; one MCP wrapper; required agent UI block | Default static runtime preflight plus explicit catalog policy; known hook forms; confined custom paths; direct/camelCase MCP maps; optional agent UI; stronger skill metadata and dependency checks |
| `scripts/update_plugin_cachebuster.py` | Second-resolution suffix; direct truncating write; arbitrary versions; empty override silently defaulted | Dry run; microsecond suffix; atomic write; preserved permissions and other fields; semver default with explicit legacy opt-in; empty override rejected |
| `scripts/read_marketplace_name.py` | Read name only | Optional `--plugin-path` checks identifier, exactly one matching entry, and local source binding before printing name |
| `scripts/identifier_validation.py` | Identifier checks | Shared semver regex also used by validator and cachebuster |
| `scripts/json_io.py` | Absent | UTF-8 JSON object reader, atomic writer, symlink refusal, marketplace-root and relative-source helpers |
| `tests/test_plugin_tools.py` | Absent | Isolated behavior regressions for scaffold, validation, registration, updates, and failure-before-write paths |
| `SKILL.md` | Contradictory hook/path/ingestion/update instructions | Executable workflows, preservation rules, accurate validation limits and marketplace discovery |
| `references/plugin-json-spec.md` | Canonical sample contradicted checker | Documented component shapes, local catalog policy, portable skill conventions and source references |
| `references/installing-and-updating.md` | Forced cachebuster/reinstall flow and obsolete discovery claims | Source verification, dry-run preparation, authorized install flow, host-aware refresh and fresh-task validation |
| `references/upgrade-notes.md` | Absent | Dated provenance, change inventory, compatibility limits, repeatable regression commands |

`agents/openai.yaml` and the skill's existing icon assets were unchanged. No pristine before-image
was saved; this behavior inventory records the observed baseline. The full current directory is the
reviewable replacement, and the tests define its important behavior.

## Compatibility and limits

Existing helper command names and the normal creation flags remain available. `--force` now preserves
existing configuration rather than resetting it; deliberate resets need an explicit separate edit.
The low-level `build_marketplace_entry` default remains `./plugins/<name>` for callers that do not
provide a path, while the CLI always passes the actual derived source. New registration mode preserves
existing dotted/underscored identifiers.

The default validator is intentionally less restrictive about publisher/UI requirements; callers
that relied on the older catalog requirements should add `--profile catalog`. That profile is local
policy, not a verified replica of the service's live ingestion schema. YAML checks use PyYAML and
standard Agent Skills metadata constraints. Unknown top-level plugin extension fields are tolerated
only in the runtime profile. Host support for such fields is not inferred.

JSON updates are atomic per file, not a transaction spanning the plugin and marketplace, and do not
lock out concurrent writers. The generator catches known source/path/configuration conflicts before
writes, but disk or permission errors can still interrupt a multi-file scaffold. Concurrent edits to
the same marketplace should be serialized by the caller. Symlinked manifests are refused on writes;
referenced components and skill assets must resolve within their allowed bundle root.

The tests do not execute hook commands, launch/authenticate MCP servers, run actual skill workflows,
install a marketplace, or verify every host-specific runtime schema. They validate the helper's real
filesystem and CLI behavior in temporary directories. A generated empty component remains a scaffold.

## Regression commands

Run from this directory:

```bash
uv run --with PyYAML python -m unittest discover -s tests -v
uv run --with PyYAML python "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator/scripts/quick_validate.py" .
uv run --with ruff ruff check --isolated --select E4,E7,E9,F,I scripts tests
python3 -m py_compile scripts/*.py tests/*.py
```

The regression suite exercises lossless force updates (including product policies, source descriptor
form, unknown metadata and order), custom marketplace roots, registration without modifying existing
files, source conflicts/duplicate entries before mutation, optional versus catalog metadata, MCP map
forms, hook override/default behavior, skill naming and invocation policy, malformed inputs, symlink
confinement, cachebuster replacement, dry-run byte preservation, and file-permission preservation.
