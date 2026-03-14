---
description: >-
  Create a Google Form for feedback and share it via Gmail. Trigger when user wants to create a google form for feedback and share it via gmail. Uses: forms, gmail.
name: recipe-create-feedback-form
version: 1.0.0
---

# Create and Share a Google Form

> **Related skills:** This recipe uses the following service skills for detailed API reference: `gws-forms`, `gws-gmail`

Create a Google Form for feedback and share it via Gmail.

## Steps

1. Create form: `gws forms forms create --json '{"info": {"title": "Event Feedback", "documentTitle": "Event Feedback Form"}}'`
2. Get the form URL from the response (responderUri field)
3. Email the form: `gws gmail +send --to attendees@company.com --subject 'Please share your feedback' --body 'Fill out the form: FORM_URL'`

