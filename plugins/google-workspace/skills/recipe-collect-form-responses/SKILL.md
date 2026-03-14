---
description: >-
  Retrieve and review responses from a Google Form. Trigger when user wants to retrieve and review responses from a google form. Uses: forms.
name: recipe-collect-form-responses
version: 1.0.0
---

# Check Form Responses

> **Related skills:** This recipe uses the following service skills for detailed API reference: `gws-forms`

Retrieve and review responses from a Google Form.

## Steps

1. List forms: `gws forms forms list` (if you don't have the form ID)
2. Get form details: `gws forms forms get --params '{"formId": "FORM_ID"}'`
3. Get responses: `gws forms forms responses list --params '{"formId": "FORM_ID"}' --format table`

