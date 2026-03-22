# Changelog

All notable changes to this project will be documented in this file.

## [0.3.0] - 2026-03-14

### Added
- 9 new service commands: /gws-drive, /gws-sheets, /gws-docs, /gws-slides, /gws-tasks, /gws-chat, /gws-people, /gws-keep, /gws-standup
- Total commands now 15 (6 quick actions + 9 service commands)

### Changed
- Modernized all 100 skill frontmatter: added version field, replaced PREREQUISITE with Related skills pattern
- Bumped version to 0.3.0
- Merged best features from google-workspace plugin

## [0.2.0] - 2026-03-14

### Added
- 100 skills total (46 core services + 10 persona + 44 recipe)
- 11 agents (1 orchestrator + 10 role-based personas)
- 6 slash commands (send-email, agenda, upload, triage, standup, meeting-prep)
- SessionStart hook for gws CLI availability check
- 5 plugin-original skills: gws-auth, gws-schema, gws-script, gws-agent-safety, gws-quick-ref
- 3 plugin-original recipes: recipe-stream-inbox, recipe-schema-explore, recipe-setup-sanitization
- Adopted 92 official skills from googleworkspace/cli repository
- Converted 10 registry personas into Claude Code agents
- Rewrote all 44 recipe skills as proper Claude Code skill content

### Changed
- Replaced 10 custom skills with 92 official skills from upstream
- Transformed OpenClaw frontmatter to Claude Code format (removed version/metadata, added triggers)
- Removed OpenClaw-specific language from all recipe bodies
