---
name: recipe-create-vacation-responder
description: "Enable a Gmail out-of-office auto-reply with a custom message and date range."
trigger:
  - keyword: vacation responder
  - keyword: out of office
  - keyword: auto reply
version: 1.0.0
---

# Set Up a Gmail Vacation Responder

Enable a Gmail out-of-office auto-reply with a custom message and date range.

## When to Use

Use this workflow when the user is going on vacation or out of office and wants to set up an automatic email response.

## Workflow

### 1. Gather details

Ask the user for:
- **Response subject** (e.g., "Out of Office")
- **Message body** (who to contact, when they return)
- **Restrict to contacts only?** (or reply to everyone)
- **Restrict to domain?** (only internal emails)

### 2. Enable the responder

```bash
gws gmail users settings updateVacation \
  --params '{"userId": "me"}' \
  --json '{"enableAutoReply": true, "responseSubject": "SUBJECT", "responseBodyPlainText": "MESSAGE", "restrictToContacts": false, "restrictToDomain": false}'
```

### 3. Verify it's active

```bash
gws gmail users settings getVacation --params '{"userId": "me"}'
```

### 4. Remind the user to disable it

When they return:

```bash
gws gmail users settings updateVacation \
  --params '{"userId": "me"}' \
  --json '{"enableAutoReply": false}'
```

## Tips

- `restrictToContacts: true` — only replies to people in your contacts
- `restrictToDomain: true` — only replies to people in your organization
- The responder can also be set with start/end dates using `startTime` and `endTime` (epoch milliseconds)
