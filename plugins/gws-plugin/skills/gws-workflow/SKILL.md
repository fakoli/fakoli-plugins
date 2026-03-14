---
name: gws-workflow
description: "Google Workflow: Cross-service productivity workflows."
trigger:
  - keyword: workflow
  - keyword: cross-service
  - keyword: automation
---

# workflow (v1)

> **Note:** See the **gws-shared** skill for auth setup, global flags, and security rules.

```bash
gws workflow <resource> <method> [flags]
```

## Helper Commands

| Command | Description |
|---------|-------------|
| [`+standup-report`](../gws-workflow-standup-report/SKILL.md) | Today's meetings + open tasks as a standup summary |
| [`+meeting-prep`](../gws-workflow-meeting-prep/SKILL.md) | Prepare for your next meeting: agenda, attendees, and linked docs |
| [`+email-to-task`](../gws-workflow-email-to-task/SKILL.md) | Convert a Gmail message into a Google Tasks entry |
| [`+weekly-digest`](../gws-workflow-weekly-digest/SKILL.md) | Weekly summary: this week's meetings + unread email count |
| [`+file-announce`](../gws-workflow-file-announce/SKILL.md) | Announce a Drive file in a Chat space |

## Discovering Commands

Before calling any API method, inspect it:

```bash
# Browse resources and methods
gws workflow --help

# Inspect a method's required params, types, and defaults
gws schema workflow.<resource>.<method>
```

Use `gws schema` output to build your `--params` and `--json` flags.

