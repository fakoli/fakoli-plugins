---
name: recipe-review-overdue-tasks
description: "Find Google Tasks that are past due and need attention."
trigger:
  - keyword: overdue tasks
  - keyword: past due
  - keyword: missed deadlines
version: 1.0.0
---

# Review Overdue Tasks

Find Google Tasks that are past due and need attention.

## When to Use

Use this workflow when the user wants to review their task lists for overdue items, catch up on missed deadlines, or prioritize what to work on next.

## Workflow

### 1. List all task lists

```bash
gws tasks tasklists list --format table
```

### 2. Check tasks in each list

For each task list (or the one the user specifies):

```bash
gws tasks tasks list \
  --params '{"tasklist": "TASKLIST_ID", "showCompleted": false}' --format table
```

### 3. Identify overdue items

Review the `due` dates and flag tasks that are past due. Present them to the user sorted by how overdue they are.

### 4. Help prioritize

Suggest which tasks to tackle first based on due date and any notes.

## Tips

- `"showCompleted": false` filters out done tasks
- Tasks without a `due` date won't show as overdue — but may still need attention
- Offer to mark tasks as complete with `gws tasks tasks patch` after the user finishes them
