---
description: >-
  Send a team announcement via both Gmail and a Google Chat space. Trigger when user wants to send a team announcement via both gmail and a google chat space. Uses: gmail, chat.
name: recipe-send-team-announcement
version: 1.0.0
---

# Announce via Gmail and Google Chat

> **Related skills:** This recipe uses the following service skills for detailed API reference: `gws-gmail`, `gws-chat`

Send a team announcement via both Gmail and a Google Chat space.

## Steps

1. Send email: `gws gmail +send --to team@company.com --subject 'Important Update' --body 'Please review the attached policy changes.'`
2. Post in Chat: `gws chat +send --space spaces/TEAM_SPACE --text '📢 Important Update: Please check your email for policy changes.'`

