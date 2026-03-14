---
name: recipe-review-meet-participants
description: "Review who attended a Google Meet conference and for how long."
trigger:
  - keyword: meet attendance
  - keyword: meeting participants
  - keyword: who attended
version: 1.0.0
---

# Review Google Meet Attendance

Review who attended a Google Meet conference and for how long.

## When to Use

Use this workflow when the user wants to check attendance for a past meeting — who joined, when they joined/left, and session duration.

## Workflow

### 1. List recent conferences

```bash
gws meet conferenceRecords list --format table
```

Ask the user which conference to review.

### 2. List participants

```bash
gws meet conferenceRecords participants list \
  --params '{"parent": "conferenceRecords/CONFERENCE_ID"}' --format table
```

### 3. Get detailed session info (optional)

For specific participants, check their session times:

```bash
gws meet conferenceRecords participants participantSessions list \
  --params '{"parent": "conferenceRecords/CONFERENCE_ID/participants/PARTICIPANT_ID"}' \
  --format table
```

### 4. Summarize

Present a summary: total attendees, join/leave times, and any notable absences.

## Tips

- Conference records are retained for a limited time — check soon after the meeting
- The `parent` parameter uses the format `conferenceRecords/CONFERENCE_ID`
