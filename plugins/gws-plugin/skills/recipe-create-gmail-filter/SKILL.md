---
name: recipe-create-gmail-filter
description: "Create a Gmail filter to automatically label, star, or categorize incoming messages."
trigger:
  - keyword: gmail filter
  - keyword: email filter
  - keyword: create filter
---

# Create a Gmail Filter

Create a Gmail filter to automatically label, star, or categorize incoming messages.

## When to Use

Use this workflow when the user wants to set up automatic email organization — routing emails from specific senders to labels, archiving notifications, or starring important messages.

## Workflow

### 1. List existing labels

See what labels already exist:

```bash
gws gmail users labels list --params '{"userId": "me"}' --format table
```

### 2. Create a new label (if needed)

```bash
gws gmail users labels create --params '{"userId": "me"}' --json '{"name": "LABEL_NAME"}'
```

Capture the label ID from the response.

### 3. Create the filter

Ask the user what criteria to match (from, to, subject, has words) and what action to take (label, archive, star, etc.):

```bash
gws gmail users settings filters create \
  --params '{"userId": "me"}' \
  --json '{"criteria": {"from": "SENDER_EMAIL"}, "action": {"addLabelIds": ["LABEL_ID"], "removeLabelIds": ["INBOX"]}}'
```

### 4. Verify

```bash
gws gmail users settings filters list --params '{"userId": "me"}' --format table
```

## Tips

- Common criteria: `from`, `to`, `subject`, `query` (Gmail search syntax)
- Common actions: `addLabelIds`, `removeLabelIds`, `star` (boolean)
- `"removeLabelIds": ["INBOX"]` archives the message (removes from inbox)
- Filters only apply to new incoming mail — existing messages are not affected
