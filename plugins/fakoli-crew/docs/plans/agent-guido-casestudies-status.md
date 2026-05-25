# Task 6 (Wave 2) — Case Studies Status

**Agent:** guido  
**Date:** 2026-05-25  
**Status:** DONE

## What was done

Created `plugins/fakoli-crew/skills/debugging/references/case-studies.md` with three worked examples of the 4-phase debugging method.

Updated `plugins/fakoli-crew/skills/debugging/SKILL.md` body (frontmatter untouched) with an "Additional Resources" section that links to `references/case-studies.md`.

## Verify output

```
word count: 1790
PASS: all criteria met
```

## Files changed

- `plugins/fakoli-crew/skills/debugging/references/case-studies.md` — new file, 1790 words
- `plugins/fakoli-crew/skills/debugging/SKILL.md` — body extended with "Additional Resources" section; frontmatter unchanged

## Case studies covered

| # | Domain | Root cause |
|---|--------|------------|
| 1 | Python / Docker | Two Python interpreters on PATH; app uses the unconfigured one |
| 2 | TypeScript / Async | Shared mutable object reference from token cache mutated mid-flight |
| 3 | Bash | Unquoted variable in glob causes word-splitting on paths with spaces |
