---
name: recipe-create-feedback-form
description: "Create a Google Form for feedback and share it via Gmail."
trigger:
  - keyword: feedback form
  - keyword: create survey
  - keyword: feedback survey
---

# Create and Share a Google Form

Create a Google Form for collecting feedback and share it via email.

## When to Use

Use this workflow when the user wants to create a feedback form, survey, or questionnaire and distribute it.

## Workflow

### 1. Create the form

```bash
gws forms forms create \
  --json '{"info": {"title": "FORM_TITLE", "documentTitle": "FORM_DOCUMENT_TITLE"}}'
```

Capture the form ID and `responderUri` from the response.

### 2. Share via email

Use `--dry-run` first:

```bash
gws gmail +send \
  --to recipients@company.com \
  --subject 'Please share your feedback' \
  --body 'We would appreciate your feedback. Please fill out this form: FORM_URL' \
  --dry-run
```

Confirm with the user, then send.

## Safety

- Always `--dry-run` before sending the email
- Confirm the recipient list with the user

## Tips

- The `responderUri` in the form creation response is the shareable link
- Add questions to the form via the Google Forms UI — the API for adding items is complex
- For simple surveys, it's faster to create the form in the UI and just use `gws` to distribute it
