---
description: Generate a standup report combining today's calendar and tasks
argument-hint: "[--format table|json]"
allowed-tools: [Bash]
---

# /gws-standup

Generate a cross-service standup report using the `gws` CLI.

## Instructions

Run the standup workflow which combines Calendar events and Tasks into a single report:

```bash
gws workflow +standup-report --format table
```

For JSON output:
```bash
gws workflow +standup-report --format json
```

## What It Includes

- Today's calendar events and meetings
- Open tasks and their status
- A combined view for daily standup preparation

## Tips

- Run this every morning to prepare for standups.
- Pair with `/gws-meeting-prep` before specific meetings.

## Error Handling

- Exit code 2: Auth expired. Tell user to run `gws auth login`.
