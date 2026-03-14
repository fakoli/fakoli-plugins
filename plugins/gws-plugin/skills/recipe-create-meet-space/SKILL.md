---
name: recipe-create-meet-space
description: "Create a Google Meet meeting space and share the join link."
trigger:
  - keyword: create meet
  - keyword: meeting link
  - keyword: new meeting room
---

# Create a Google Meet Conference

Create a Google Meet meeting space and share the join link.

## When to Use

Use this workflow when the user needs a quick meeting link without creating a calendar event, or wants to set up a standing meeting room.

## Workflow

### 1. Create the meeting space

```bash
gws meet spaces create --json '{"config": {"accessType": "OPEN"}}'
```

Capture the meeting URI from the response.

### 2. Share the link

Ask the user how they want to share — email, chat, or just display:

**Via email:**

```bash
gws gmail +send \
  --to recipients@company.com \
  --subject 'Join the meeting' \
  --body 'Join here: MEETING_URI' \
  --dry-run
```

**Via chat:**

```bash
gws chat +send --space spaces/SPACE_ID --text 'Meeting link: MEETING_URI'
```

**Or just display** the link to the user.

## Safety

- Always `--dry-run` before sending emails with the link

## Tips

- `"accessType": "OPEN"` means anyone with the link can join
- Use `"accessType": "TRUSTED"` to restrict to organization members
