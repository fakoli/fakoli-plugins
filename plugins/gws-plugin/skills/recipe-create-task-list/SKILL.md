---
name: recipe-create-task-list
description: "Set up a new Google Tasks list with initial tasks."
trigger:
  - keyword: create task list
  - keyword: new task list
  - keyword: setup tasks
---

# Create a Task List and Add Tasks

Set up a new Google Tasks list with initial tasks.

## When to Use

Use this workflow when the user wants to create a new task list and populate it with initial items.

## Workflow

### 1. Create the task list

```bash
gws tasks tasklists insert --json '{"title": "TASK_LIST_NAME"}'
```

Capture the task list ID from the response.

### 2. Add tasks

For each task the user wants to add:

```bash
gws tasks tasks insert \
  --params '{"tasklist": "TASKLIST_ID"}' \
  --json '{"title": "TASK_TITLE", "notes": "OPTIONAL_NOTES", "due": "DUE_DATE_ISO8601"}'
```

### 3. Verify

```bash
gws tasks tasks list --params '{"tasklist": "TASKLIST_ID"}' --format table
```

## Tips

- Due dates must be in ISO 8601 format: `2026-04-01T00:00:00Z`
- Tasks can have `notes` for additional context
- Leave `due` out of the JSON if the task has no deadline
