---
name: gws-auth
description: Check or configure gws CLI authentication, account selection, OAuth scopes, and credential sources for a requested Google Workspace workflow.
---

# gws authentication

Read [shared conventions](../gws-shared/SKILL.md). Check `gws auth status` and `gws auth --help` first. Use `gws auth login --help` to verify the installed version's scope and account flags; default presets and credential backends have changed across CLI releases.

- Existing authorized account: reuse it if it matches the task; do not log out, replace credentials, or expand scopes routinely.
- First-time setup: `gws auth setup` can change Google Cloud configuration. Use it when setup is requested, after identifying the intended project/account.
- OAuth login: `gws auth login` opens an interactive browser. The user performs sign-in/consent. Select only services/scopes needed by the task, for example `gws auth login --scopes drive,gmail,calendar`; verify the installed CLI accepts these names.
- Automation: use a supported existing credential source such as `GOOGLE_WORKSPACE_CLI_TOKEN` or `GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE`. Read current CLI help/docs for service-account and keyring support. Workspace admin APIs may require domain delegation and admin approval; possession of a service account does not grant it.
- Auth failure: inspect structured error/status, correct an account/scope mismatch, and retry only the authorized action. A service/API failure does not automatically justify login or wider scopes.

Never run `gws auth export` as routine diagnosis or display token/key material. Auth status may identify an account, but it does not prove access to every Workspace service. Use a minimal requested read to verify the relevant permission.

See [upstream authentication](https://github.com/googleworkspace/cli#authentication), reviewed 2026-09-05. The upstream project is not an officially supported Google product.
