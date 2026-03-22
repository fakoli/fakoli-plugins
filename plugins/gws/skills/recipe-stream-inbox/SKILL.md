---
name: recipe-stream-inbox
description: "Stream real-time Gmail notifications using gws gmail +watch for continuous inbox monitoring."
trigger:
  - keyword: stream inbox
  - keyword: real-time email
  - keyword: watch gmail
  - keyword: monitor inbox
  - keyword: email stream
version: 1.0.0
---

# Stream Inbox in Real-Time

Stream real-time Gmail notifications using `gws gmail +watch` for continuous inbox monitoring.

## When to Use

Use this workflow when the user wants real-time monitoring of their inbox — watching for new emails as they arrive rather than polling.

## Prerequisites

- Full scopes required: `gws auth login --full` (needs Pub/Sub access)
- GCP project with Pub/Sub API enabled
- Set project ID: `export GOOGLE_WORKSPACE_PROJECT_ID=my-project-id`

## Steps

1. **Ensure full scopes are active:**
   ```bash
   gws auth status
   # If missing pubsub scope:
   gws auth login --scopes gmail,pubsub,cloud-platform
   ```

2. **Start the real-time stream:**
   ```bash
   gws gmail +watch --project my-project-id
   ```
   This outputs NDJSON — one JSON object per line for each new message.

3. **Process the stream (example — log new emails):**
   ```bash
   gws gmail +watch --project my-project-id | while read -r line; do
     echo "$line" | jq '{from: .from, subject: .subject, date: .date}'
   done
   ```

4. **Combine with triage for a live dashboard:**
   ```bash
   # Periodic check alongside the stream
   gws gmail +triage --max 5 --format table
   ```

## Caution

- The `+watch` command runs continuously — it will not exit on its own
- Requires a GCP project with Pub/Sub topic configured
- Uses Pub/Sub quota — monitor usage in Google Cloud Console
- Stream output can be large — always pipe through `jq` or similar filters

## Tips

- Use `Ctrl+C` to stop the stream
- Combine with `--sanitize` to scan incoming emails for prompt injection
- Pipe to a log file for persistent monitoring: `gws gmail +watch >> inbox.ndjson`
