---
name: recipe-setup-sanitization
description: "Configure Google Cloud Model Armor globally for all gws commands to protect against prompt injection in API responses."
trigger:
  - keyword: setup sanitization
  - keyword: model armor setup
  - keyword: prompt injection protection
  - keyword: configure sanitize
  - keyword: content safety setup
---

# Set Up Global Response Sanitization

Configure Google Cloud Model Armor to scan all `gws` API responses for prompt injection before they reach AI agents.

## When to Use

Use this workflow when the user wants to set up response sanitization — either globally for all commands or for specific high-risk operations like reading untrusted emails.

## Prerequisites

- GCP project with Model Armor API enabled
- Full scopes: `gws auth login --full`

## Steps

1. **Create a Model Armor template:**
   ```bash
   gws modelarmor +create-template \
     --project my-project-id \
     --location us-central1 \
     --template my-safety-template
   ```

2. **Test sanitization on a single command:**
   ```bash
   gws gmail users messages get \
     --params '{"userId": "me", "id": "MSG_ID"}' \
     --sanitize "projects/my-project-id/locations/us-central1/templates/my-safety-template"
   ```

3. **Enable globally via environment variables:**
   ```bash
   # Add to your .env or shell profile
   export GOOGLE_WORKSPACE_CLI_SANITIZE_TEMPLATE="projects/my-project-id/locations/us-central1/templates/my-safety-template"
   export GOOGLE_WORKSPACE_CLI_SANITIZE_MODE=warn
   ```

4. **Choose a mode:**

   | Mode | Behavior |
   |------|----------|
   | `warn` (default) | Logs a warning but returns the response |
   | `block` | Returns an error if injection is detected |

5. **Verify it's active:**
   ```bash
   # Any gws command will now show sanitization status in debug logs
   GOOGLE_WORKSPACE_CLI_LOG=gws=debug gws gmail +triage
   ```

6. **Make it permanent — add to `.env` file:**
   ```bash
   cat >> .env << 'EOF'
   GOOGLE_WORKSPACE_CLI_SANITIZE_TEMPLATE=projects/my-project-id/locations/us-central1/templates/my-safety-template
   GOOGLE_WORKSPACE_CLI_SANITIZE_MODE=warn
   EOF
   ```

## Per-Command Override

Even with global sanitization, you can override per-command:

```bash
# Use a different template for sensitive operations
gws gmail users messages get \
  --params '{"userId": "me", "id": "MSG_ID"}' \
  --sanitize "projects/P/locations/L/templates/strict-template"
```

## Caution

- Model Armor adds latency to each API call (sanitization is an extra network hop)
- `block` mode will cause commands to fail if injection is detected — use `warn` initially
- Monitor Model Armor quota and costs in Google Cloud Console

## Tips

- Start with `warn` mode to understand your baseline before switching to `block`
- Use `block` mode for high-risk operations (e.g., reading untrusted emails)
- Combine with `--fields` to reduce the amount of text being sanitized
- Check logs with `GOOGLE_WORKSPACE_CLI_LOG=gws=debug` to see sanitization results
