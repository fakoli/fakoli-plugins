---
name: recipe-send-team-announcement
description: "Send a team announcement via both Gmail and a Google Chat space."
trigger:
  - keyword: team announcement
  - keyword: announce to team
  - keyword: broadcast message
version: 1.0.0
---

# Announce via Gmail and Google Chat

Send a team announcement via both Gmail and a Google Chat space.

## When to Use

Use this workflow when the user needs to broadcast a message to the team through multiple channels — email for the record, chat for immediate visibility.

## Workflow

### 1. Compose the announcement

Ask the user for:
- **Subject/title**
- **Message body**
- **Email recipients** (team distribution list)
- **Chat space** for the chat notification

### 2. Send the email

```bash
gws gmail +send \
  --to team@company.com \
  --subject 'SUBJECT' \
  --body 'MESSAGE_BODY' \
  --dry-run
```

Confirm, then send.

### 3. Post in Chat

```bash
gws chat +send \
  --space spaces/SPACE_ID \
  --text 'CHAT_MESSAGE'
```

### 4. Confirm

Tell the user both channels have been notified.

## Safety

- Always `--dry-run` the email before sending
- Confirm the chat space is correct before posting
- Double-check the recipient list for email

## Tips

- Keep the Chat message shorter than the email — link to the email for details
- Use `--html` for formatted email announcements
