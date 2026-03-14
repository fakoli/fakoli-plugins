---
name: recipe-collect-form-responses
description: "Retrieve and review responses from a Google Form."
trigger:
  - keyword: form responses
  - keyword: collect responses
  - keyword: check form
version: 1.0.0
---

# Check Form Responses

Retrieve and review responses from a Google Form.

## When to Use

Use this workflow when the user wants to check responses to a Google Form, review survey results, or collect feedback data.

## Workflow

### 1. Find the form

If the user doesn't have the form ID, help them find it:

```bash
gws forms forms list --format table
```

### 2. Review form structure

Check what questions the form contains:

```bash
gws forms forms get --params '{"formId": "FORM_ID"}' --fields "info,items"
```

### 3. Get responses

```bash
gws forms forms responses list --params '{"formId": "FORM_ID"}' --format table
```

### 4. Summarize for the user

Present the responses in a readable format — count responses, highlight trends, or summarize answers.

## Tips

- Use `--format table` for a quick visual overview
- Use `--format json` if you need to process or filter responses programmatically
- For forms with many responses, the output can be large — summarize rather than showing raw data
