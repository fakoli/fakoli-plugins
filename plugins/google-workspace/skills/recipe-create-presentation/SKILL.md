---
description: >-
  Create a new Google Slides presentation and add initial slides. Trigger when user wants to create a new google slides presentation and add initial slides. Uses: slides.
name: recipe-create-presentation
version: 1.0.0
---

# Create a Google Slides Presentation

> **Related skills:** This recipe uses the following service skills for detailed API reference: `gws-slides`

Create a new Google Slides presentation and add initial slides.

## Steps

1. Create presentation: `gws slides presentations create --json '{"title": "Quarterly Review Q2"}'`
2. Get the presentation ID from the response
3. Share with team: `gws drive permissions create --params '{"fileId": "PRESENTATION_ID"}' --json '{"role": "writer", "type": "user", "emailAddress": "team@company.com"}'`

