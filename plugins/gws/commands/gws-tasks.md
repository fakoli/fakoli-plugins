---
description: List, create, complete, and manage Google Tasks
argument-hint: "<list|create|complete|delete> [task-title | task-id]"
allowed-tools: [Bash]
---

# /gws-tasks

Manage Google Tasks using the `gws` CLI.

## Instructions

When this command is invoked, parse `$ARGUMENTS` to determine the operation.

### Common Operations

**List task lists:**
```bash
gws tasks tasklists list --format table
```

**List tasks in default list:**
```bash
gws tasks tasks list --params '{"tasklist": "@default"}' --format table
```

**Create a task:**
```bash
gws tasks tasks insert --params '{"tasklist": "@default"}' --json '{"title": "Task title", "notes": "Details"}'
```

**Create a task with due date:**
```bash
gws tasks tasks insert --params '{"tasklist": "@default"}' --json '{"title": "Task title", "due": "2026-03-20T00:00:00Z"}'
```

**Complete a task:**
```bash
gws tasks tasks patch --params '{"tasklist": "@default", "task": "TASK_ID"}' --json '{"status": "completed"}'
```

**Delete a task:**
```bash
gws tasks tasks delete --params '{"tasklist": "@default", "task": "TASK_ID"}'
```

## Tips

- Due dates must be in RFC 3339 format (e.g., `2026-03-20T00:00:00Z`).
- Task status values: `needsAction` (open), `completed`.
- Use `--dry-run` before delete operations.

## Error Handling

- Exit code 2: Auth expired. Tell user to run `gws auth login`.
