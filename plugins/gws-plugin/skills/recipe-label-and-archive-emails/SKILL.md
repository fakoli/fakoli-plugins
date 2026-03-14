---
name: recipe-label-and-archive-emails
description: "Apply Gmail labels to matching messages and archive them to keep your inbox clean."
trigger:
  - keyword: label emails
  - keyword: archive emails
  - keyword: organize inbox
---

# Label and Archive Gmail Threads

Apply Gmail labels to matching messages and archive them to keep your inbox clean.

## When to Use

Use this workflow when the user wants to organize their inbox — label emails from a specific sender/subject and move them out of the inbox.

## Workflow

### 1. Find matching emails

```bash
gws gmail users messages list \
  --params '{"userId": "me", "q": "SEARCH_QUERY"}' \
  --fields "messages(id)" --format table
```

Ask the user for the search criteria (sender, subject, keywords).

### 2. Find or create the target label

List existing labels:

```bash
gws gmail users labels list --params '{"userId": "me"}' --format table
```

Create a new one if needed:

```bash
gws gmail users labels create --params '{"userId": "me"}' --json '{"name": "LABEL_NAME"}'
```

### 3. Apply label and archive

For each message:

```bash
gws gmail users messages modify \
  --params '{"userId": "me", "id": "MESSAGE_ID"}' \
  --json '{"addLabelIds": ["LABEL_ID"], "removeLabelIds": ["INBOX"]}'
```

### 4. Report results

Tell the user how many messages were labeled and archived.

## Tips

- `"removeLabelIds": ["INBOX"]` is what archives the message
- You can apply multiple labels at once: `"addLabelIds": ["LABEL_1", "LABEL_2"]`
- Consider suggesting a Gmail filter (recipe-create-gmail-filter) for ongoing automation
