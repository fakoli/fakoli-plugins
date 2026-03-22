# Plugin Validation Report — fakoli-speak

**Date:** 2026-03-21
**Reviewer:** Plugin Validator (Claude Code)
**Plugin root:** `/Users/sdoumbouya/code/sekoudoumbouy.com/fakoli-plugins/plugins/fakoli-speak/`

---

## Summary

The plugin is structurally sound and passes all critical schema checks. Two confirmed bugs were found: all seven command files use the wrong YAML frontmatter key (`allowed_tools` instead of `allowed-tools`), which means Claude Code will not honor the tool restriction at all. One warning-level issue was found in the hooks file (missing `matcher` is legal but not best practice in this version). The README is significantly out of date relative to the current feature set and will mislead new users. A `.gitignore` is absent, leaving the `.venv` directory unguarded. No security issues were found.

**Result: FAIL** — one confirmed functional bug (wrong frontmatter key on every command) must be fixed before publishing.

---

## 1. Manifest — `.claude-plugin/plugin.json`

**Status: PASS**

| Field | Value | Assessment |
|---|---|---|
| `name` | `fakoli-speak` | Valid kebab-case |
| `version` | `2.0.0` | Valid semver |
| `description` | 155-char multi-provider summary | Clear and accurate |
| `author.name` | `Sekou Doumbouya` | Present |
| `author.url` | `https://github.com/fakoli` | Valid HTTPS URL |
| `repository` | `https://github.com/fakoli/fakoli-plugins` | Valid HTTPS URL |
| `license` | `MIT` | Matches LICENSE file |
| `keywords` | 11 entries | Valid array |

No auto-discovered directories (`commands`, `agents`, `skills`, `hooks`) are declared in the manifest. The plugin correctly relies on filesystem auto-discovery for all components.

No unknown fields found. No hardcoded credentials. No HTTP (non-HTTPS) URLs.

---

## 2. Commands — `commands/*.md`

**Status: FAIL** — one bug present across all 7 files.

### Bug: `allowed_tools` should be `allowed-tools` (Major — all 7 files)

Claude Code's YAML frontmatter key is `allowed-tools` (hyphen-separated), matching the official SDK convention used in all Anthropic-published plugins (confirmed against `claude-plugins-official/code-review` and `claude-plugins-official/plugin-dev`). The underscore variant (`allowed_tools`) is silently ignored — Claude will not restrict tool use, so the Bash tool restriction has no effect.

**Affected files:**
- `commands/speak.md` — line 3
- `commands/autospeak.md` — line 3
- `commands/cost.md` — line 3
- `commands/provider.md` — line 3
- `commands/status.md` — line 3
- `commands/stop.md` — line 3
- `commands/voices.md` — line 3

**Fix:** Replace `allowed_tools: Bash` with `allowed-tools: Bash` in all 7 files.

### `description` field — PASS

All 7 command files have a non-empty `description` in frontmatter.

| File | Description |
|---|---|
| `speak.md` | "Read the last response aloud using TTS" |
| `autospeak.md` | "Toggle automatic text-to-speech for all responses" |
| `cost.md` | "Show TTS usage and cost tracking" |
| `provider.md` | "Show or switch the active TTS provider" |
| `status.md` | "Check TTS playback status and configuration" |
| `stop.md` | "Stop TTS playback" |
| `voices.md` | "List available voices for the active TTS provider" |

### `${CLAUDE_PLUGIN_ROOT}` references — PASS

All 7 command files use `${CLAUDE_PLUGIN_ROOT}` correctly in their bash invocations. No hardcoded absolute paths were found. The pattern `cd ${CLAUDE_PLUGIN_ROOT} && uv run fakoli-speak <subcommand>` is consistent across all commands.

### Markdown content — PASS

All files have substantive markdown body content beyond the frontmatter. No broken file references were found (commands do not reference any external files).

### Missing `argument-hint` — Minor

`speak.md`, `autospeak.md`, `cost.md`, and `provider.md` accept implicit arguments (e.g., "on"/"off" for autospeak, `--reset`/`--rate` for cost, provider name for provider) but none of the command files declare an `argument-hint` frontmatter field. This is optional but improves the Claude Code command palette UX.

---

## 3. Hooks — `hooks/hooks.json`

**Status: PASS with one warning.**

### Schema structure — PASS

The file is valid JSON with the correct top-level structure:

```
{
  "description": string,        ✓ present and non-empty
  "hooks": {                    ✓ required wrapper key present
    "Stop": [                   ✓ valid event name
      {
        "matcher": "*",         ✓ present
        "hooks": [              ✓ inner hooks array present
          {
            "type": "command",  ✓ valid type
            "command": "cd ${CLAUDE_PLUGIN_ROOT} && uv run fakoli-speak autospeak-hook",
            "async": true,      ✓ valid boolean
            "timeout": 30       ✓ valid integer (seconds)
          }
        ]
      }
    ]
  }
}
```

The structure matches the established schema used by other plugins in this registry (safe-fetch, ralph-loop, gws).

### `${CLAUDE_PLUGIN_ROOT}` in hook command — PASS

The hook command uses `${CLAUDE_PLUGIN_ROOT}` correctly. The pattern `cd ${CLAUDE_PLUGIN_ROOT} && uv run ...` is consistent with the command files.

### Warning: `matcher: "*"` on a `Stop` event

The `Stop` event fires once per session stop regardless of tool context. A wildcard matcher is technically correct but redundant — `Stop` hooks have no tool context to match against. This is not a bug but may indicate the matcher field was copied from a `PreToolUse`/`PostToolUse` template. Some plugin schemas omit `matcher` on `Stop` events entirely (e.g., `ralph-loop/hooks.json`). No change is required but the matcher field is effectively inert here.

---

## 4. `${CLAUDE_PLUGIN_ROOT}` References — PASS

All occurrences of `${CLAUDE_PLUGIN_ROOT}` across commands and hooks were verified:

- 7 command files: `cd ${CLAUDE_PLUGIN_ROOT} && uv run fakoli-speak <subcommand>` — correct
- 1 hooks file: `cd ${CLAUDE_PLUGIN_ROOT} && uv run fakoli-speak autospeak-hook` — correct

No hardcoded absolute paths found. No relative paths found. The variable is used exclusively for the `cd` anchor to ensure `uv` resolves the project's `pyproject.toml`.

---

## 5. Auto-discovered Directories Not Declared in `plugin.json` — PASS

The manifest contains no `commands`, `agents`, `skills`, or `hooks` keys. Auto-discovery is used correctly for all components. No conflict between explicit declaration and filesystem discovery.

---

## 6. `README.md` — PASS (exists) / Warning (content)

The file exists at `/Users/sdoumbouya/code/sekoudoumbouy.com/fakoli-plugins/plugins/fakoli-speak/README.md`.

**Warning: README is out of date relative to version 2.0.0**

The README was written for v1.x (ElevenLabs-only). The plugin now supports 5 providers (OpenAI, ElevenLabs, Deepgram, Google Gemini, macOS Say) as stated in `plugin.json`'s description and reflected in `commands/provider.md`. Specific inaccuracies:

- **Title section:** "ElevenLabs text-to-speech for Claude Code" — should say "Multi-provider TTS for Claude Code"
- **Requirements:** Only lists `ELEVENLABS_API_KEY` — other providers require different env vars
- **Commands table:** Missing `/provider` command (present in the commands directory)
- **Configuration table:** Only shows 3 ElevenLabs-specific vars — no mention of `FAKOLI_SPEAK_PROVIDER`, OpenAI, Deepgram, or Google env vars
- **Cost tracking section:** Only shows v1 cost commands; `--json` flag not present in `cost.md` instructions

A user reading the README would not know `/provider` exists or how to configure any provider other than ElevenLabs.

---

## 7. `LICENSE` — PASS

MIT License file is present at `/Users/sdoumbouya/code/sekoudoumbouy.com/fakoli-plugins/plugins/fakoli-speak/LICENSE`. Copyright year is 2025, copyright holder is Sekou Doumbouya. License field in `plugin.json` (`"MIT"`) matches.

---

## 8. Additional Findings

### Missing `.gitignore` — Warning

No `.gitignore` file exists in the plugin root. The plugin contains a `.venv/` directory (a Python virtual environment with hundreds of files from pytest, pygments, packaging, pluggy, etc.). Without a `.gitignore`, `.venv` will be committed to git and included in any published plugin archive. This significantly bloats the plugin.

Recommended minimum `.gitignore`:
```
.venv/
__pycache__/
*.egg-info/
*.pyc
.pytest_cache/
dist/
build/
```

### No `agents/` or `skills/` directories — expected

The plugin correctly does not include agents or skills directories. No validation needed.

### No security issues found

- No hardcoded API keys or secrets in any plugin file
- No HTTP (non-HTTPS) URLs in manifest or hooks
- The `~/.env` pattern used for secrets is correct
- Hook commands do not expose any secrets

---

## Component Summary

| Component | Count | Valid | Issues |
|---|---|---|---|
| Commands | 7 | 7 (description) | 7 wrong frontmatter key |
| Agents | 0 | — | — |
| Skills | 0 | — | — |
| Hooks | 1 file | 1 (schema valid) | matcher warning |
| MCP Servers | 0 | — | — |

---

## Positive Findings

- `plugin.json` is clean and accurate — good semver, proper kebab-case name, multi-provider description matches reality
- Every command file has a clear, concise `description` field
- `${CLAUDE_PLUGIN_ROOT}` is used consistently and correctly in every invocation
- No auto-discovered directories are redundantly declared in the manifest
- `hooks.json` has the correct `hooks` → event → matcher → `hooks` nesting structure
- Hook uses `async: true` on the Stop event, which is the right pattern for a non-blocking TTS trigger
- LICENSE and README both exist
- No hardcoded credentials anywhere in the plugin

---

## Recommendations (Priority Order)

1. **Fix `allowed_tools` → `allowed-tools` in all 7 command files.** This is the only functional bug. Until fixed, Claude Code will ignore the tool restriction entirely.

2. **Update README.md to reflect v2.0.0.** Rewrite the provider-specific sections to document all 5 providers, add `/provider` to the commands table, and update the configuration table with all env vars.

3. **Add a `.gitignore` that excludes `.venv/`, `__pycache__/`, and `*.egg-info/`.** The `.venv` directory is already present on disk and will pollute any git commit or plugin archive.

4. **Add `argument-hint` to commands that accept arguments.** Specifically `autospeak.md` (`on|off`), `provider.md` (`<name>`), `cost.md` (`--reset | --rate <rate>`). This improves the command palette experience.

5. **Consider removing the `matcher` field from the `Stop` hook** or documenting why it is kept. The wildcard on a `Stop` event is inert but harmless.

---

## Overall Assessment

**FAIL** — The plugin has one confirmed functional bug: `allowed_tools` (underscore) is not a recognized Claude Code frontmatter key. The correct key is `allowed-tools` (hyphen). This bug is present in all 7 command files and must be fixed before the plugin is published or distributed. All other components are structurally correct and well-organized. The fix is mechanical and low-risk.
