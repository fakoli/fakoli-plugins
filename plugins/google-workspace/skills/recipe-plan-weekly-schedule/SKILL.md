---
description: >-
  Review your Google Calendar week, identify gaps, and add events to fill them. Trigger when user wants to review your google calendar week, identify gaps, and add events to fill them. Uses: calendar.
name: recipe-plan-weekly-schedule
version: 1.0.0
---

# Plan Your Weekly Google Calendar Schedule

> **Related skills:** This recipe uses the following service skills for detailed API reference: `gws-calendar`

Review your Google Calendar week, identify gaps, and add events to fill them.

## Steps

1. Check this week's agenda: `gws calendar +agenda`
2. Check free/busy for the week: `gws calendar freebusy query --json '{"timeMin": "2025-01-20T00:00:00Z", "timeMax": "2025-01-25T00:00:00Z", "items": [{"id": "primary"}]}'`
3. Add a new event: `gws calendar +insert --summary 'Deep Work Block' --start '2026-01-21T14:00:00' --end '2026-01-21T16:00:00'`
4. Review updated schedule: `gws calendar +agenda`

