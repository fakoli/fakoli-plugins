# Task 2 (Wave 1) — Iron Rule Reference: Status

**Agent:** guido  
**Task:** Create shared Iron Rule reference  
**Status:** COMPLETE

## Output

File created: `plugins/fakoli-crew/skills/crew-ops/references/iron-rule.md`

## Verification

- File exists: yes
- Word count: 338 (limit: 500)
- Verify command passed: `test -f ... && [ "$(wc -w < ...)" -lt 500 ]` — exit 0

## Source Review

Read the following files to extract existing Iron Rule wordings before writing the canonical version:

- `agents/smith.md` (lines 44-46) — "Never modify a file you have not read in full in this session. Plugin failures are almost always caused by a one-line change made without seeing the surrounding configuration."
- `agents/keeper.md` (lines 58-62) — Same opening sentence; framing around infrastructure drift and sources of truth staying in sync.
- `agents/critic.md` (lines 58-60) — "Read EVERY file in scope before making a single comment. No drive-by reviews."
- `agents/welder.md` (lines 81-83) — "Never modify a file you have not read in this session."

## Decisions

- Imperative voice throughout; no "you should" or "the agent must" phrasing.
- Kept the production-incident framing from smith and keeper as the justification paragraph.
- The "How to Announce Compliance" section is original — none of the agent files modeled the announcement pattern, but the task requested it.
- Final line lists all six bound agents as specified.
- Agent files are untouched — Task 7 (Wave 2) will replace duplicated prose with pointers to this file.
