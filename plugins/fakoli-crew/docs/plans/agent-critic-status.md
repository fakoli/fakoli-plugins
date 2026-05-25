# Critic Gate — Wave 2 Re-Review (Fix Cycle 1)

**Scope (re-review only — 3 files modified by welder):**
- `skills/crew-ops/references/agent-roster.md` — herald row color fix
- `agents/guido.md` — Iron Rule pointer replacing inline prose
- `agents/sentinel.md` — `allowed-tools` → `tools` in Section 4 checklist and description example

**Reviewed by:** critic
**Date:** 2026-05-25

---

## Fix Verification

### Fix 1 — agent-roster.md herald row color

**Status: CORRECT**

Line 14 of the current file reads:

```
| herald | pink | Documentation writer | READMEs, marketplace descriptions, branding, user-facing copy | `agents/herald.md` |
```

The color is `pink`, matching `agents/herald.md` frontmatter. The change is surgical — all other seven rows are byte-for-byte identical to what they were before the fix (guido=blue, critic=red, scout=cyan, smith=green, welder=yellow, keeper=purple, sentinel=orange). No collateral damage.

---

### Fix 2 — guido.md Iron Rule pointer

**Status: CORRECT**

Line 98 in the current file reads:

```
1. Read all relevant files before making any recommendation. Use Glob and Read to understand the current structure. **Iron Rule:** See `skills/crew-ops/references/iron-rule.md`.
```

The inline prose — "Never recommend a change to a file you have not read in this session" — is gone. The canonical pointer is present. The numbered list in the "Your Process" section is intact: items `1.` through `7.` all present, no broken list markers, no orphaned text before or after item 1.

---

### Fix 3 — sentinel.md `allowed-tools` → `tools`

**Status: CORRECT**

Two locations were updated as welder documented:

1. **Section 4 checklist (line 95):**
   ```
   - Has `name`, `description`, `model`, `color`, `tools` in frontmatter.
   ```
   Correct. The stale `allowed-tools` field name is replaced.

2. **Third `<example>` block, assistant response (lines 36–37):**
   ```
   Validating the PR: checking frontmatter fields (name, description, model,
   color, tools), verifying the agent is listed in CLAUDE.md and marketplace.json,
   ```
   Correct. The frontmatter field list in the example now matches what agent files actually contain.

3. **Sentinel's own frontmatter (lines 47–51):** Verified intact — `tools:` is present with the correct four-tool list (`Read`, `Bash`, `Glob`, `Grep`). The frontmatter was not altered by the fix.

A `grep -n "allowed-tools"` across all three files returns zero results, confirming complete remediation.

---

## New Issues Introduced

None. All three fixes are mechanical string replacements confined to exactly the targeted locations. No YAML frontmatter was touched in any of the three files. No list structure was disrupted. No cross-references were introduced or broken.

---

## Previously Open Items (Unchanged — Out of Scope for This Cycle)

The following items from the Wave 2 report remain open and were explicitly not part of Fix Cycle 1. They are carried forward as-is:

| # | Severity | File | Issue |
|---|----------|------|-------|
| 4 | CONSIDER | `welder.md:94` | Addendum prose after iron-rule link may drift over time |
| 5 | CONSIDER | `crew-ops/SKILL.md:3` | Description field opens with "This skill should be used when" |
| 6 | NIT | `debugging/SKILL.md:72` | Additional Resources uses bare path, not a markdown link |
| 7 | NIT | `iron-rule.md:40` | Bound-agents list does not explain why scout/sentinel are omitted |

None of these block Wave 3.

---

## VERDICT: PASS

All 2 MUST FIX items and 1 SHOULD FIX item from the Wave 2 report are resolved correctly. No new issues were introduced. The three modified files have sound YAML frontmatter, intact markdown structure, and accurate cross-references.

Wave 3 (version bump + registry regeneration) is unblocked.

Status: PASS
