# Changelog

## 1.1.1 (2026-06-01)

### Added
- `references/status-protocol.md` now back-references fakoli-style **P10** (tool scratch lives outside version control), linking the `.fakoli/runs/` scratch root to its operating-model principle. Docs-only.

---

## 1.1.0 (2026-06-01)

### Changed
- Status files now write to a gitignored per-run scratch root `.fakoli/runs/<run-id>/` (orchestrator-injected absolute path) instead of `docs/plans/`.

---

## 1.0.1 (2026-05-24)

Evaluation-audit patch release. No skill semantics or workflow logic changed — all fixes are documentation, frontmatter, and structural.

### Fixed
- Piped-grep antipattern in `hooks/detect-context.sh` replaced with a captured-variable + here-string pattern; added a non-empty guard so the script no longer emits a half-formed context line if `claude plugin list` returns nothing

### Changed
- `skills/execute/SKILL.md` slimmed by extracting two reference blocks: the Status File Format inline block now points at the existing `references/status-protocol.md` (which already had the full spec), and the 22-line example dispatch prompt moved to a new `references/example-dispatch-prompt.md`. Execute body now 2,131 words (down from over the 2,200 target)
- Added inline citations of `references/wave-engine-ref.md` and `docs/wave-engine.md` in the execute skill's Wave Assignment section
- `commands/flow.md` metadata strengthened: added `argument-hint: ""` (the `/flow` command is intentionally argument-less; routing is via `/flow:<skill-name>`), added a "How invocation works" section explaining the distinction, and synced all 6 per-skill descriptions in the table to match each SKILL.md frontmatter exactly (every row had drifted)
- `skills/quick/SKILL.md` gained a one-line "Agent selection" preview in the Overview pointing at the routing matrix in Step 3
- Moved `research/superpowers-feedback.md` → `docs/research/superpowers-feedback.md` and added a "Background research" section to the README pointing at it; empty `research/` directory removed

---

## 1.0.0 (2026-04-04)

### Added
- Initial release of fakoli-flow
- 6 skills: brainstorm, plan, execute, verify, finish, quick
- Intent-driven orchestration philosophy (plans describe WHAT, not HOW)
- Wave engine with parallel agent dispatch and critic gates
- Visual companion with PID tracking and auto-restart
- SessionStart hook for language and crew detection
- `/flow` command showing skills and project state
- Documentation: intent-driven-orchestration.md, wave-engine.md, getting-started.md
- References: wave-engine-ref.md, status-protocol.md
