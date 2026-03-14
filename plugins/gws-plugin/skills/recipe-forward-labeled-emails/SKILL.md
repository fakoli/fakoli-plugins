---
name: recipe-forward-labeled-emails
description: "Find Gmail messages with a specific label and forward them to another address."
trigger:
  - keyword: forward labeled
  - keyword: forward emails by label
  - keyword: auto forward
---

# Forward Labeled Gmail Messages

Find Gmail messages with a specific label and forward them to another address.

## When to Use

Use this workflow when the user wants to forward a batch of labeled emails to someone (e.g., forwarding "needs-review" emails to a manager).

## Workflow

### 1. Find labeled messages

```bash
gws gmail users messages list \
  --params '{"userId": "me", "q": "label:LABEL_NAME"}' \
  --fields "messages(id)" --format table
```

### 2. Review message contents

For each message (or a subset), get the details:

```bash
gws gmail users messages get \
  --params '{"userId": "me", "id": "MSG_ID"}' \
  --fields "payload.headers,snippet"
```

Show the user which messages will be forwarded.

### 3. Forward each message

For each message, use `--dry-run` first:

```bash
gws gmail +forward \
  --message MSG_ID \
  --to recipient@company.com \
  --dry-run
```

Confirm with the user, then send.

## Safety

- Always preview message subjects/senders before forwarding
- Use `--dry-run` on the first forward to confirm format
- Ask the user to confirm the full batch before sending

## Tips

- Use Gmail's `+forward` helper instead of composing new emails — it preserves the thread
- You can also use `gws gmail +send` with the original content if `+forward` doesn't fit the use case
