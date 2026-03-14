---
description: >-
  Review who attended a Google Meet conference and for how long. Trigger when user wants to review who attended a google meet conference and for how long. Uses: meet.
name: recipe-review-meet-participants
version: 1.0.0
---

# Review Google Meet Attendance

> **Related skills:** This recipe uses the following service skills for detailed API reference: `gws-meet`

Review who attended a Google Meet conference and for how long.

## Steps

1. List recent conferences: `gws meet conferenceRecords list --format table`
2. List participants: `gws meet conferenceRecords participants list --params '{"parent": "conferenceRecords/CONFERENCE_ID"}' --format table`
3. Get session details: `gws meet conferenceRecords participants participantSessions list --params '{"parent": "conferenceRecords/CONFERENCE_ID/participants/PARTICIPANT_ID"}' --format table`

