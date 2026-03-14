---
name: gws-auth
description: "Authenticate and manage credentials for the gws CLI — login, logout, status, scopes, service accounts, and credential storage."
trigger:
  - keyword: gws auth
  - keyword: gws login
  - keyword: authenticate
  - keyword: credentials
  - keyword: oauth
  - keyword: service account
  - keyword: gws setup
---

# gws auth

> **Note:** See the **gws-shared** skill for global flags and security rules.

Manage authentication and credentials for the `gws` CLI.

## Auth Subcommands

```bash
gws auth login       # Interactive OAuth2 login (opens browser)
gws auth logout      # Remove stored credentials
gws auth setup       # Guided first-run setup wizard
gws auth status      # Show current auth state and active scopes
gws auth export      # Export credentials for use in other tools
```

## Login Options

### Minimal scopes (default — safest for unverified apps)

```bash
gws auth login
```

Default scopes: Drive, Sheets, Gmail, Calendar, Docs, Slides, Tasks.

### Full scopes (includes Pub/Sub and Cloud Platform)

```bash
gws auth login --full
```

Adds `pubsub` and `cloud-platform` scopes. Requires a verified OAuth app or Workspace domain admin approval.

### Custom scopes

```bash
gws auth login --scopes drive,gmail,sheets,pubsub
```

Unrecognized service names are resolved dynamically from Discovery docs.

### Read-only access

```bash
gws auth login --readonly
```

Grants only `.readonly` scopes for all services.

## Credential Sources (Priority Order)

1. **`GOOGLE_WORKSPACE_CLI_TOKEN`** — Pre-obtained OAuth2 access token (highest priority)
2. **`GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE`** — Path to OAuth credentials JSON
3. **Encrypted credentials** — AES-256-GCM encrypted at `~/.config/gws/`
4. **`GOOGLE_APPLICATION_CREDENTIALS`** — Standard Google ADC (fallback)

## Service Account Support

```bash
export GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE=/path/to/service-account.json
gws drive files list
```

## Credential Storage

- Credentials are stored at `~/.config/gws/` (override with `GOOGLE_WORKSPACE_CLI_CONFIG_DIR`)
- Encrypted with AES-256-GCM
- Encryption key stored in OS keyring by default
- For headless/Docker/CI: `export GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND=file`

## Environment Variables

| Variable | Description |
|---|---|
| `GOOGLE_WORKSPACE_CLI_TOKEN` | Pre-obtained OAuth2 access token |
| `GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE` | Path to OAuth credentials JSON |
| `GOOGLE_WORKSPACE_CLI_CLIENT_ID` | OAuth client ID |
| `GOOGLE_WORKSPACE_CLI_CLIENT_SECRET` | OAuth client secret |
| `GOOGLE_WORKSPACE_CLI_CONFIG_DIR` | Override config directory |
| `GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND` | `keyring` (default) or `file` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Standard Google ADC path |

## Common Workflows

### First-time setup

```bash
gws auth setup          # Guided wizard
gws auth status         # Verify it worked
gws gmail +triage       # Test with a read operation
```

### Check current status

```bash
gws auth status
```

### Re-authenticate with broader scopes

```bash
gws auth login --scopes drive,gmail,sheets,calendar,pubsub,cloud-platform
```

## Tips

- Start with `gws auth login` (minimal scopes) — add more later with `--scopes`
- Use `gws auth status` to verify permissions before running commands
- For CI/CD, set `GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND=file` and provide credentials via env vars
- Never share or log the output of `gws auth export`
