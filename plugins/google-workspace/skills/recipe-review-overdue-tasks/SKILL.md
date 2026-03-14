---
description: >-
  Find Google Tasks that are past due and need attention. Trigger when user wants to find google tasks that are past due and need attention. Uses: tasks.
name: recipe-review-overdue-tasks
version: 1.0.0
---

# Review Overdue Tasks

> **Related skills:** This recipe uses the following service skills for detailed API reference: `gws-tasks`

Find Google Tasks that are past due and need attention.

## Steps

1. List task lists: `gws tasks tasklists list --format table`
2. List tasks with status: `gws tasks tasks list --params '{"tasklist": "TASKLIST_ID", "showCompleted": false}' --format table`
3. Review due dates and prioritize overdue items

