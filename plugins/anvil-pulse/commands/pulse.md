---
description: Start, stop, or check the anvil-pulse live dashboard for this project
---

Use the `pulse` skill from the anvil-pulse plugin to handle this request.

Arguments: $ARGUMENTS

- No arguments or `start` -> start the dashboard for the current project and
  give the user the URL.
- `stop` -> stop the dashboard for the current project.
- `status` or `check` -> report whether the dashboard is running and where.
- `statusline` -> walk through installing the optional Claude Code statusline
  segment (requires explicit user confirmation before editing their script).
