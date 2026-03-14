---
name: recipe-post-mortem-setup
description: "Create a Google Docs post-mortem, schedule a Google Calendar review, and notify via Chat."
trigger:
  - keyword: post mortem
  - keyword: incident review
  - keyword: post-mortem setup
version: 1.0.0
---

# Set Up Post-Mortem

Create a post-mortem document, schedule a review meeting, and notify the team — all in one workflow.

## When to Use

Use this workflow after an incident when the user needs to set up the post-mortem process: create a structured document, schedule a review meeting, and notify the team.

## Workflow

### 1. Gather incident details

Ask the user for:
- **Incident name** (e.g., "API Outage 2026-03-14")
- **Team/attendees** for the review meeting
- **Preferred review time**
- **Chat space** for the notification

### 2. Create the post-mortem document

```bash
gws docs +write \
  --title 'Post-Mortem: INCIDENT_NAME' \
  --body '## Summary\n\n## Timeline\n\n## Root Cause\n\n## Impact\n\n## Action Items\n\n## Lessons Learned'
```

Capture the document ID.

### 3. Schedule the review meeting

```bash
gws calendar +insert \
  --summary 'Post-Mortem Review: INCIDENT_NAME' \
  --attendee team@company.com \
  --start 'REVIEW_TIME' \
  --end 'REVIEW_END_TIME' \
  --dry-run
```

Confirm, then execute.

### 4. Notify the team in Chat

```bash
gws chat +send \
  --space spaces/SPACE_ID \
  --text 'Post-mortem scheduled for INCIDENT_NAME. Doc: DOC_LINK | Review: MEETING_TIME'
```

### 5. Share the document

```bash
gws drive permissions create \
  --params '{"fileId": "DOC_ID"}' \
  --json '{"role": "writer", "type": "user", "emailAddress": "team@company.com"}'
```

## Safety

- Use `--dry-run` on the calendar event and chat message before executing
- Confirm the attendee list and chat space with the user

## Tips

- Share the doc with `writer` access so the team can contribute
- Include the doc link in the calendar event description
