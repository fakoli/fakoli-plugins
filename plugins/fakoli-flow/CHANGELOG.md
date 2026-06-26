# Changelog

## 1.3.5 (2026-06-26)

### Fixed
- Updated the fakoli-flow design spec to refer to the renamed
  `systems-thinking` marketplace plugin identity.

---

## 1.3.4 (2026-06-26)

### Fixed
- Replaced unsupported short `/flow` and `/flow:<skill>` examples with the
  Claude Code plugin namespace, `/fakoli-flow:flow` and
  `/fakoli-flow:<skill>`, after live smoke tests confirmed the short alias is
  not routed by Claude Code.

---

## 1.3.3 (2026-06-26)

### Fixed
- Synced README version badge to the current marketplace manifest.

---

## 1.3.2 (2026-06-10)

### Added
- `docs/specs/2026-06-11-flow-on-native-agent-teams.md`: design spec mapping the wave engine onto Anthropic's native Agent Teams. Targets the stack's biggest strategic opportunity (superpowers #429, 112 reactions, asks for exactly this). Key moves: the hook-enforced critic gate re-expresses from a `PreToolUse`-deny workaround onto `TaskCompleted` exit-2 (per-task, parallel-safe — the platform event whose semantic *is* the gate); fakoli delegates dispatch/claiming/file-locks/status-transport to the platform (the anvil) and keeps the intent-plan format, gate policy, evidence rules, and durable state (the hammers); fakoli-state becomes the source of truth under the explicitly-ephemeral native task list. Docs-only; no behavior change.

---

## 1.3.1 (2026-06-10)

### Changed
- Generic-fallback substitution table (graceful degradation without fakoli-crew) gains a `warden` row, so the security-audit gate degrades to a `general-purpose` security reviewer instead of being silently dropped when fakoli-crew is absent.

---

## 1.3.0 (2026-06-10)

### Added
- **Adversarial refutation pass in `/fakoli-flow:verify` (Step 5.5).** After the sentinel produces its scorecard, a second sentinel is dispatched as a REFUTER: for every PASS it attempts to break the verdict with its own commands, a stricter criterion reading, or an edge case. A criterion is PASS only when both sentinels agree; every REFUTED verdict flips to FAIL carrying the refuter's evidence. Adopted from the adversarial-convergence pattern in Anthropic's Dynamic Workflows — independent refutation materially outperforms single-verifier review. Skipped only when there are no PASS verdicts to refute; generic-fallback runs self-refute before reporting

---

## 1.2.0 (2026-06-09)

### Added
- **System-enforced critic gate.** New `hooks/gate-track.sh` (PostToolUse) and `hooks/gate-check.sh` (PreToolUse) on agent dispatch: while a run is armed via `.fakoli/gate-armed`, completing a code-writing crew agent (guido/smith/welder) sets the gate PENDING, and only critic or welder dispatches are permitted until a critic review completes. A welder fix re-pends the gate, so fix cycles mechanically require critic re-review. Fail-open (24h stale-arm expiry, `FAKOLI_FLOW_NO_GATE=1`, `rm .fakoli/gate-armed`). The gate moves from prompt-level convention to hook-level enforcement — closing the gap flagged in the design review between what the docs claim ("cannot be skipped") and what the system guaranteed
- Execute skill: arm/disarm protocol in Step 1 and Final Summary; critic dispatch prompt upgraded to two-stage review (Stage 1 spec compliance with `[SPEC]`-labeled MUST FIX, Stage 2 code quality) — adopted from superpowers' two-stage review split
- Execute + verify skills: sentinel dispatch prompts now require a machine-readable fenced-JSON verdict block (`{"verdict", "pass", "fail", "na", "failures": [{"check", "fix_owner"}]}`) so the orchestrator can branch on results without scraping prose

### Changed
- Run-ID format gains seconds (`YYYYMMDDHHmmss`) plus explicit basename sanitization rules (lowercase, `[a-z0-9-]`, collapse dashes) — same-minute runs of one plan no longer collide on a scratch root
- `hooks/detect-context.sh`: crew version detection no longer hard-codes the `fakoli-plugins` marketplace cache path; falls back through plugin-list output → any cache/marketplace location

---

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
- `commands/flow.md` metadata strengthened: added `argument-hint: ""` (the `/fakoli-flow:flow` command is intentionally argument-less; routing is via `/fakoli-flow:<skill-name>`), added a "How invocation works" section explaining the distinction, and synced all 6 per-skill descriptions in the table to match each SKILL.md frontmatter exactly (every row had drifted)
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
- `/fakoli-flow:flow` command showing skills and project state
- Documentation: intent-driven-orchestration.md, wave-engine.md, getting-started.md
- References: wave-engine-ref.md, status-protocol.md
