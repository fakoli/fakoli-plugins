---
description: List or run the verify commands this repo requires for the current changes
---

Use the `gate-check` skill from the gate-router plugin for: $ARGUMENTS

- No argument or `list` -> show what the current diff requires.
- `run` -> execute the gates, stop on first failure, report it verbatim.
- `init` -> help the user author .claude/gate-router.local.md from the repo's
  CI steps and CLAUDE.md test instructions.
