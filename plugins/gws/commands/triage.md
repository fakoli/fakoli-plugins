---
description: Show unread email inbox summary
argument-hint: "[query]"
allowed-tools: Bash(gws:*)
---

# /triage

Show an unread email inbox summary using the `gws` CLI.

## Instructions

1. If the user provides a query argument, use it as the `--query` flag. Otherwise, show all unread.

2. Run the triage command:
   ```bash
   gws gmail +triage --format table
   ```
   Or with a query:
   ```bash
   gws gmail +triage --query '<QUERY>' --format table
   ```

3. Present the results showing sender, subject, and date.

4. If there are many results, suggest using `--max N` to limit.

5. Offer to read specific messages or reply if the user wants to take action on any email.
