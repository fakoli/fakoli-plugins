<!--
INTENTIONAL ANTIPATTERNS — DO NOT FIX
=====================================

This fixture is a deliberately-broken SKILL.md used to smoke-test
fakoli-crew's `skill-critic` per the procedure in tests/RECIPES.md (T7).

The following bugs are intentional. If you "fix" them, skill-critic will
no longer surface a finding and the smoke test will regress.

Intentional bugs:
  1. Vague description ("a skill that helps with things").
     Expected critic finding: SHOULD FIX (or MUST FIX per skill-critic's
     bar — vague capability claims are flagged because they cause silent
     trigger failure: Claude reads the description to decide when to load
     the skill, and a vague phrase will never match concrete user phrasing).

  2. No decision flow / no numbered steps.
     Expected critic finding: SHOULD FIX — multi-step skills MUST present
     their flow either as a numbered workflow ("Step 1 — ...", "Step 2 — ...")
     or an explicit decision table. This skill is a wall of prose with no
     enumerated steps and no decision branches called out.

Expected verdict from skill-critic when run against this file: FAIL
(2x SHOULD FIX findings minimum; possibly 1 MUST FIX for the description
depending on how strictly the agent treats the vague-capability bar).
-->
---
name: bad-skill
description: a skill that helps with things
---

# bad-skill

This skill helps when things need to happen. It does what is needed and then
finishes. Depending on the situation it might do one thing or another thing.
The user can call this skill whenever they want and it should generally work
out for them.

When invoked, consider the situation and do the appropriate action. If the
situation is unclear, try to clarify it. If clarification fails, fall back to
a reasonable default. The default depends on context but usually involves
checking some files and then maybe writing some output somewhere sensible.

Output is whatever feels right for the situation. There's no fixed format
because every situation is different. Use judgment.

There are no numbered steps in this skill because the skill is too flexible
for a fixed workflow. The agent should just figure it out.
