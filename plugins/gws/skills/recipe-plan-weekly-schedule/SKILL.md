---
name: recipe-plan-weekly-schedule
description: "Review your Google Calendar week, identify gaps, and add events to fill them."
trigger:
  - keyword: plan week
  - keyword: weekly schedule
  - keyword: weekly planning
version: 1.0.0
---

# Plan Your Weekly Google Calendar Schedule

Review your Google Calendar week, identify gaps, and add events to fill them.

## When to Use

Use this workflow when the user wants to plan their week — review what's scheduled, find open slots, and add new events.

## Workflow

### 1. Review the current week

```bash
gws calendar +agenda --week --format table
```

### 2. Check free/busy status

```bash
gws calendar freebusy query \
  --json '{"timeMin": "WEEK_START_ISO8601", "timeMax": "WEEK_END_ISO8601", "items": [{"id": "primary"}]}'
```

### 3. Identify gaps and suggest events

Analyze the schedule and present free slots to the user. Suggest what they might want to add (focus time, 1:1s, planning sessions, etc.).

### 4. Add new events

For each event the user wants to add, use `--dry-run` first:

```bash
gws calendar +insert \
  --summary 'EVENT_TITLE' \
  --start 'START_TIME' \
  --end 'END_TIME' \
  --dry-run
```

### 5. Review the updated schedule

```bash
gws calendar +agenda --week --format table
```

## Safety

- Always `--dry-run` before creating events

## Tips

- Use `gws calendar +agenda` (no flags) for just today's view
- The agenda helper uses the account's timezone automatically
