# Task 5 (Wave 1) Status — Add trigger phrases to debugging skill description

**Agent:** guido  
**Status:** DONE  
**File changed:** `plugins/fakoli-crew/skills/debugging/SKILL.md`

## What was done

Augmented the `description:` frontmatter field in `SKILL.md` with a trailing sentence containing 5 literal quoted user phrases:

- `"why is this failing"`
- `"this test keeps failing"`
- `"I've tried three fixes"`
- `"root cause"`
- `"systematic debugging"`

The existing scenario sentences were retained unchanged. The body of the file was not touched. The final description is 71 words (under the 80-word limit).

## Verify result

```
awk '/^---$/{c++; next} c==1' plugins/fakoli-crew/skills/debugging/SKILL.md \
  | tr ',' '\n' | grep -c '"[a-zA-Z][^"]*"' \
  | awk '{exit ($1<5)}'
```

Exit code: 0 (PASS — 5+ quoted phrases present in frontmatter)
