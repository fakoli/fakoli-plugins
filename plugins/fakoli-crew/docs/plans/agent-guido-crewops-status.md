# Status: agent-guido — Task 4 (Wave 2) crew-ops SKILL.md

**Status:** COMPLETE

**Task:** Bring `skills/crew-ops/SKILL.md` into spec compliance with `plugin-dev:skill-development`.

## Files Modified

- `plugins/fakoli-crew/skills/crew-ops/SKILL.md`

## Changes Made

1. **Trigger phrases added to frontmatter `description:`** — appended a trigger-phrases segment with 7 literal quoted phrases: "assemble a crew", "who owns this file", "plan the waves", "run the crew on X", "coordinate agents to Y", "which agent should handle", "multi-agent orchestration". Existing scenario language was preserved and augmented.

2. **Opening line rewritten to imperative form** — changed "Use this skill to orchestrate multi-agent work." to "To orchestrate multi-agent work, assign one owner per file…". First substantive non-heading line now begins with an imperative verb phrase, not second-person framing.

3. **Inline 8-row agents table removed** — replaced with a single pointer line: "See `skills/crew-ops/references/agent-roster.md` for the full 8-agent roster with roles, colors, and file paths." This links to the canonical roster created by Task 3.

4. **"Skills" subsection split into two distinct subsections** — the mixed table (which conflated a slash command `/crew` with a real skill `Debugging`) was removed. Replaced with:
   - `## Companion Command` — documents `/crew`
   - `## Related Skill` — documents `debugging`

## Acceptance Criteria Verification

| Criterion | Result |
|-----------|--------|
| Trigger phrases in frontmatter | PASS |
| Opening line not "Use this skill" | PASS |
| `agent-roster.md` referenced | PASS |
| Word count < 700 (actual: 472) | PASS |
| `name: crew-ops` unchanged | PASS |
| Full verify command | PASS |

## Decisions

- Kept trigger phrases inline in the `description:` string (quoted within the YAML string) rather than as a separate `triggers:` field — the task says "augment, do not replace" and the spec uses description-level trigger guidance.
- Used `## Companion Command` and `## Related Skill` as distinct H2 subsections rather than a flat list — this matches the "clean separation" language in the acceptance criteria and makes each item individually scannable.
