# Scout Status — cli-to-plugin spec verification

**Status:** COMPLETE
**Date:** 2026-05-24

---

## Findings

### 1. uv + PEP 723

**Current uv version on this machine:** `uv 0.10.9 (f675560f3 2026-03-06)`

**Confirmed working:** Both `uv run <script.py>` and `uv run --script <script.py>` work for PEP 723 scripts. The `-s / --script` flag is a first-class uv flag ("Run the given path as a Python script"), confirmed via `uv run --help`.

**Exact syntax for the PEP 723 block:**
```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0"]
# ///
```
The block must appear at the top of the file as comment lines. Both `uv run discover.py` and `uv run --script discover.py` resolve the block and create an isolated venv with the declared deps.

**Stdlib-only scripts:** Work fine with PEP 723 block present (`dependencies = []`). Also work without any block at all — uv just runs the file directly. Evidence:
```
$ uv run /tmp/test_pep723.py   # stdlib-only with block
Python 3.11.15 ... stdlib-only PEP 723 works
```

**With real dependencies:** Auto-installs on first run, cached thereafter. Evidence:
```
$ uv run /tmp/test_pep723_dep.py   # pyyaml dependency
Installed 1 package in 13ms
pyyaml loaded: {'key': 'value'}
```

**The `--script` flag distinction:** `--script` tells uv to treat the file as an isolated PEP 723 script even if there is a `pyproject.toml` in the working directory. Without `--script`, uv may try to run it as a project member if a `pyproject.toml` is present nearby. For `discover.py`, which lives inside `plugins/cli-to-plugin/scripts/` alongside a potential `pyproject.toml`, **use `uv run --script` explicitly** to guarantee isolation.

**macOS-specific gotchas:** None documented or observed. Tested on Darwin 25.5.0 (macOS 26+), Clang 21.1.4, Python 3.11.15. No issues.

**The spec's invocation `uv run --script discover.py gh`** is correct syntax. The flag is real and works.

---

### 2. Marketplace schemas

**`schemas/skill.schema.json` — what it requires and constrains:**

- `additionalProperties: false` — any frontmatter key not in the schema is rejected.
- All fields are optional (no `required` array). A valid SKILL.md frontmatter can be just `name` + `description`.
- `name`: string, `maxLength: 64`. No pattern constraint (no kebab enforcement in schema, though docs recommend it).
- `description`: string, **no maxLength**. Uncapped. The spec's long "Use when working with GitHub pull requests..." descriptions are fine.
- `argument-hint`: string (hyphenated key, not `argument`).
- `disable-model-invocation`: boolean.
- `user-invocable`: boolean.
- `allowed-tools`: string (comma-separated), not array.
- `model`, `context`, `agent`, `hooks`: also defined.

**Critical schema/template discrepancy found:** The `templates/basic/skills/example/SKILL.md` uses `user_invocable: true` (underscore). The schema defines `user-invocable` (hyphen). Since the schema has `additionalProperties: false`, the underscore form would be rejected if schema-validated. The generator should use `user-invocable` (hyphen). No existing production SKILL.md files in `plugins/` use either form — so the template is the only place this is wrong.

**`schemas/plugin.schema.json` — what it requires and constrains:**

- `required: ["name"]` — only `name` is required.
- `name`: pattern `^[a-z0-9-]+$`, min 2, max 64 chars. The keyword `"cli-to-plugin"` in the generated plugin's keywords array must also match `^[a-z0-9-]+$` (it does).
- `description`: `minLength: 10`, `maxLength: 500`. The spec's example description ("Use the `gh` CLI through Claude...") is 90 chars — well within limits. The generator must enforce both bounds.
- `author`: the schema accepts `oneOf [string, object]`. **However, `validate.sh` is stricter than the schema** — it explicitly rejects non-object authors (line 164: `if [[ "$author_type" != "object" ]]; then log_error`). The generated `plugin.json` must use the object form `{"name": "..."}`, not a plain string.
- `keywords`: array of strings, each matching `^[a-z0-9-]+$`, uniqueItems. The spec example keywords (`"gh"`, `"github"`, `"cli"`, `"generated"`, `"cli-to-plugin"`) all pass. The generator must enforce this pattern when using override-supplied keywords.

**Suitability for generator validation:** Both schemas are directly usable for validating generated artifacts. `python -m jsonschema` (via uv) can validate against them. The `validate.sh` script adds checks beyond the schema (author object enforcement, license file check) so it remains the authoritative validation step.

**Spec constraint missed:** The spec's `plugin.json` template shows `"license": "MIT"` with no LICENSE file in the generated plugin. `validate.sh` will emit a `WARN` for this (not ERROR) — the Summary block should list it as an expected warning. The spec's summary example already does this: "validate.sh: missing LICENSE file (recommended)". No blocker.

---

### 3. Marketplace validation scripts

**`validate.sh` CLI signature:**
```
./scripts/validate.sh [plugin-path]
```
- With no argument: validates all plugins in `plugins/` and `external_plugins/`, then validates `marketplace.json`.
- With one argument: validates that single plugin directory.
- Exit codes: `exit 1` if `FAILED > 0`, `exit 0` otherwise.
- Output: colored human-readable text to stdout/stderr. No machine-readable output format.

**`test-path-resolution.sh` CLI signature:**
```
./scripts/test-path-resolution.sh [plugin-path]
```
- With no argument: scans all plugins in `plugins/` and `external_plugins/`.
- With one argument: scans that single plugin directory.
- Exit codes: `exit 1` if `ERRORS > 0`, `exit 0` otherwise.
- Output: colored human-readable text to stdout/stderr.

**Can they validate a plugin outside `plugins/`?** **Yes, confirmed.** Both scripts accept an absolute path to any directory. They resolve the plugin root from the supplied argument, not from `ROOT_DIR`. The schema file path is always resolved relative to the script's own location (`ROOT_DIR/schemas/plugin.schema.json`), so the schemas are always found regardless of where the plugin lives.

Evidence — ran against the template (which lives at `templates/basic/`, outside `plugins/`):
```
$ ./scripts/validate.sh /path/to/fakoli-plugins/templates/basic
...
Passed: 11  Warnings: 1  Failed: 0
```
```
$ ./scripts/test-path-resolution.sh /path/to/fakoli-plugins/templates/basic
...
Passed: 0  Warnings: 0  Errors: 0
```

**Implication for `validate-output.sh`:** The script can pass an absolute path to the generated plugin in a temp dir (e.g., `/tmp/cli-to-plugin-output/gh`) and both validators will work correctly.

---

### 4. Existing patterns

**Template (`templates/basic/`):**
- Layout: `.claude-plugin/plugin.json`, `skills/example/SKILL.md`, `README.md`, `CHANGELOG.md`, `Makefile`.
- No `commands/` directory — the template is skills-only.
- Good baseline for the generated plugin shape (which is also skills-only).

**Python scripts in existing plugins:**

Two distinct patterns exist:

1. **Project-style (`pyproject.toml` in plugin root):** Used by `nano-banana-pro` and `safe-fetch` and `fakoli-state`. Invoked as `uv run --directory "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/scripts/foo.py"`. Requires a `pyproject.toml` at the plugin root, which uv uses for dependency resolution.

2. **Bare stdlib script (no metadata):** `nano-banana-pro/skills/generate/scripts/nanobanana.py` is documented as "Stdlib-only (urllib + base64 + regex)" and has no PEP 723 block. It's called via the project-style invocation above (using the plugin-root `pyproject.toml` for the env).

**No existing plugin uses PEP 723 inline `# /// script` metadata.** The `cli-to-plugin` plugin will be the first.

**Slash commands with playbook pattern:**
- `notebooklm-enhanced/commands/` — multiple `.md` command files acting as step-by-step playbooks (e.g., `setup.md`, `generate.md`).
- `marketplace-manager/commands/` — `add-plugin.md`, `remove-plugin.md`, `scan-plugins.md` — all pure markdown playbooks; Claude reads and executes the steps.
- `nano-banana-pro/commands/configure.md` — best reference for an interactive multi-step command that asks the user questions inline (Step 1 check → Step 2 create → Step 3 configure per-setting → Step 4 gitignore). Claude drives the interaction by following the numbered step structure.

**AskUserQuestion evidence:** The only references to `AskUserQuestion` in the entire repo are in the spec file itself and one plan document. No existing command file calls it by name — command playbooks instead direct Claude to "ask the user for X" or "confirm with the user" inline, which Claude translates into natural conversation. The `nano-banana-pro/commands/configure.md` is the closest pattern: "Ask the user for their Gemini API key." This is equivalent to what the spec calls `AskUserQuestion` — it's Claude's built-in conversational ability, not a separate tool call. The playbook in `cli-to-plugin.md` should follow the same convention: instruct Claude to "ask the user to confirm the groups (show a list, ask which to skip)" rather than referencing a specific tool name.

---

### 5. Naming conflicts

No plugin named `cli-to-plugin` exists in `plugins/`. No similar names found:
```
$ ls plugins/ | grep -i "cli\|converter\|wrapper\|generator"
(no output)
```
Archive directory (`archive/`) contains: `k8s-sidecar-testing`, `README.md`, `rust-network-module`. No conflict.

`cli-to-plugin` is valid by the name pattern (`^[a-z0-9-]+$`, 13 chars, within 2–64 range). No reserved-name list exists in the codebase.

---

### 6. AskUserQuestion availability inside slash commands

Confirmed: slash commands are markdown playbooks that Claude reads and executes. There is no tool named `AskUserQuestion` that Claude calls explicitly — Claude handles user interaction conversationally as directed by the playbook prose.

Evidence from `nano-banana-pro/commands/configure.md`:
- "Ask the user for their Gemini API key" — Claude asks conversationally.
- "Ask which default model to use" — Claude presents options and waits for input.
- No tool invocation syntax anywhere in the file.

The spec's phrase "user picks via `AskUserQuestion` multi-select" means: Claude presents a numbered or bulleted list and asks the user to reply with their selections. The playbook should describe the desired interaction in natural language (e.g., "Show the user the list of proposed groups. Ask them which to skip, if any. Wait for their response before proceeding."). Claude handles the back-and-forth.

Multi-select specifically: the playbook should instruct Claude to present a numbered list and ask the user to "reply with the numbers to skip" or "reply with the numbers of meta-skills to generate." This is standard Claude conversational behavior, no special tool needed.

---

### 7. `gh` CLI on this machine

```
$ which gh
/opt/homebrew/bin/gh

$ gh --version
gh version 2.92.0 (2026-04-28)
https://github.com/cli/cli/releases/tag/v2.92.0
```

Present and current. The spec's canonical example (`gh`) is directly testable. The help tree fixture in `tests/fixtures/` should be captured from this version.

---

### 8. uv on this machine

```
$ which uv
/Users/sdoumbouya/.local/bin/uv

$ uv --version
uv 0.10.9 (f675560f3 2026-03-06)
```

Present. Required for `discover.py` execution and for `uv run --with pytest pytest plugins/cli-to-plugin/tests/`. Both work as expected (tested above).

---

### 9. `jq` and `ajv` availability

```
$ which jq
/usr/bin/jq  (version: jq-1.7.1-apple)

$ which ajv
ajv not found
```

`ajv` is **not present**. It is an npm package and would require Node.js + a global npm install — an unreasonable dev dependency for a Python/shell plugin.

`python -m jsonschema` is available via uv with zero friction:
```
$ uv run --with jsonschema python -c "import jsonschema; print(jsonschema.__version__)"
Installed 6 packages in 13ms
4.26.0
```

**Recommendation:** Replace the `ajv` call in `validate-output.sh` with:
```bash
uv run --with jsonschema python -m jsonschema -i <file> <schema>
```
This is Node-free, installs on first run, and works identically to ajv for JSON Schema Draft 2020-12 validation. The `jsonschema` library supports Draft 2020-12 (the `$schema` used in this repo's schemas) since v4.18+.

---

## Recommendations for plan tasks

- **Use `uv run --script` (with the `-s` flag) for `discover.py` invocations** inside the playbook, not bare `uv run`. This ensures isolation even if a `pyproject.toml` exists at the plugin root. Example: `uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/discover.py" gh`.

- **For `discover.py` tests**, use the project-style invocation (`uv run --with pytest pytest ...`) rather than PEP 723 in the test files themselves. Match the pattern in `fakoli-state/bin/pyproject.toml`.

- **Replace `ajv` with `uv run --with jsonschema python -m jsonschema`** in `validate-output.sh`. Drop any Node dependency from the spec.

- **Generate `author` as an object** `{"name": "..."}`, never a plain string. `validate.sh` rejects the string form even though the JSON schema allows it.

- **Use hyphenated frontmatter keys in generated SKILL.md files**: `user-invocable`, `disable-model-invocation`, `argument-hint`, `allowed-tools`. The schema enforces `additionalProperties: false` so the underscored template form (`user_invocable`) would fail validation.

- **The `description` field in `plugin.json` has `minLength: 10`** — the generator must enforce this when constructing the description. Short CLI names (e.g., `aws`) might produce short descriptions if the generator is naive. Add a minimum-length guard.

- **Both validation scripts accept absolute paths outside `plugins/`.** The `validate-output.sh` helper can pass the full absolute path to the generated plugin in any temp or output directory — no need to move it into `plugins/` first.

- **The playbook (`cli-to-plugin.md`) should phrase user interactions as natural-language instructions to Claude** ("Present the list of groups. Ask the user which to skip, if any. Wait for their reply."), not as tool call syntax. There is no `AskUserQuestion` tool — Claude handles this conversationally.

- **Capture the `gh` help tree fixture** using `gh version 2.92.0` (current on this machine) for the `tests/fixtures/` directory. Note the version in the fixture file name or a `meta` field so future test failures distinguish "script broke" from "CLI changed."

- **The spec lists `schemas/skill.schema.json` for SKILL.md validation.** The schema has no `required` fields and no `description` maxLength. Generated files only need `name` and `description` in frontmatter to be valid. The generator does not need to produce all optional fields.

- **`cli-to-plugin` as a keyword** (`"cli-to-plugin"`) passes the keyword pattern `^[a-z0-9-]+$`. Safe to use.

- **No LICENSE file in the generated plugin** will produce a `validate.sh` WARN (not ERROR). This is expected and already accounted for in the spec's summary block example. The plan should note this as a known non-blocking warning.

---

## Blockers (if any)

None. All spec assumptions are confirmed. The plan can proceed without spec revision.

The one notable discrepancy (schema says `author` can be string; `validate.sh` requires object) is already handled in the spec's `plugin.json` example, which uses the object form. No revision needed.
