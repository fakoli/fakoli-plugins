# Active Plugin Review — 2026-06-26

Scope: every active plugin under `plugins/`.

Verification baseline:
- `for d in plugins/*/; do python -m json.tool "$d/.claude-plugin/plugin.json" > /dev/null || echo "BAD MANIFEST: $d"; done`
- `./scripts/validate.sh`
- `./scripts/test-path-resolution.sh`

## Reviewed Plugins

| Plugin | Result | Findings / action |
|---|---|---|
| `cli-to-plugin` | Fixed | Added missing `CHANGELOG.md`; clarified that the full spec path is repository-local documentation. |
| `excalidraw-diagram` | Fixed | Added changelog entries so release notes match marketplace metadata. |
| `fakoli-crew` | Fixed | Synced README badge and current roster/count references from 8 to 9 agents. Historical release notes and archived plans remain unchanged. |
| `fakoli-flow` | Fixed / deferred | Synced README badge. Deferred runtime verification of `/flow:<skill>` suffix routing to the Claude/Codex compatibility tasks (`T012` / `T013`) because it requires runtime capability discovery rather than static docs review. |
| `fakoli-plugin-critic` | OK | Manifest, README, changelog, license, and five-agent surface were consistent. |
| `fakoli-speak` | Fixed | Added missing `2.0.x` changelog notes and corrected `/voices` to document `OPENAI_TTS_VOICE`. |
| `fakoli-state` | Fixed | Synced README release copy and declared `.mcp.json` via `mcpServers` in the manifest. |
| `fakoli-style` | Fixed | Added standard `[Unreleased]` section and sharpened skill trigger metadata. |
| `gws` | Fixed | Renamed agent `allowed_tools` frontmatter keys to `tools`; removed unsupported `trigger` / `version` skill frontmatter; fixed standup command docs and changelog drift. |
| `handoff` | Fixed | Replaced unsupported `author.github` metadata with `author.url`; added slash-command wrappers matching README and hook banner. |
| `marketplace-manager` | Fixed | Documented `/scan-plugins`; updated authoring guidance from stale `extended.*` and JSON component filenames to current manifest/component conventions. |
| `nano-banana-pro` | Fixed | Renamed agent `allowed-tools` frontmatter keys to `tools`; normalized command argument frontmatter; synced package metadata and changelog. |
| `notebooklm-enhanced` | Fixed | Documented `notebooklm-core`; clarified research-agent delegation; synced changelog/package metadata. |
| `quick-notes` | Fixed | Fixed `export-notes.py` to write `notes.md` next to the active notes log instead of plugin code; added regression coverage. |
| `safe-fetch` | Fixed | Updated `/fetch` to use `$ARGUMENTS`; removed unsupported skill `version`; aligned search docs with `country` / `city` parameters. |
| `session-retro` | Fixed | Added advertised `/session-retro` command; corrected `user-invocable`; aligned output-location descriptions. |

## Deferred Items

- `fakoli-flow` slash suffix routing (`/flow:brainstorm`, `/flow:quick`, etc.) should be verified in `T012` / `T013`, where the PRD explicitly calls for Claude Code vs Codex capability discovery.
- Historical docs and changelog entries that accurately described older releases were left intact even when they mention older agent counts, model defaults, or versions.
