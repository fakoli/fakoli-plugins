# Changelog

All notable changes to this project will be documented in this file.

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
