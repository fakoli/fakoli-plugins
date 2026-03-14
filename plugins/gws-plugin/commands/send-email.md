---
description: Send an email via Google Workspace CLI
argument-hint: "[to] [subject]"
allowed-tools: Bash(gws:*)
---

# /send-email

Send an email using the `gws` CLI.

## Instructions

1. Parse the user's argument for recipient(s) and subject. If not provided, ask the user for:
   - **To:** recipient email address(es)
   - **Subject:** email subject line
   - **Body:** email body content

2. First run with `--dry-run` to show what will be sent:
   ```bash
   gws gmail +send --to <EMAILS> --subject '<SUBJECT>' --body '<BODY>' --dry-run
   ```

3. Show the user the dry-run output and ask for confirmation.

4. On confirmation, run the actual send command (remove `--dry-run`).

5. Report success with the message ID.

## Options
- Add `--cc` or `--bcc` if the user mentions CC/BCC recipients
- Add `--html` if the user provides HTML content
- For attachments, explain that the raw API must be used instead
