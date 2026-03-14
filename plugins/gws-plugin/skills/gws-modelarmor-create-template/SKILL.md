---
name: gws-modelarmor-create-template
description: "Google Model Armor: Create a new Model Armor template."
trigger:
  - keyword: create armor template
  - keyword: modelarmor template
  - keyword: safety template
version: 1.0.0
---

# modelarmor +create-template

> **Reference:** See the `gws-shared` skill for auth, global flags, and security rules.

Create a new Model Armor template

## Usage

```bash
gws modelarmor +create-template --project <PROJECT> --location <LOCATION> --template-id <ID>
```

## Flags

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--project` | ✓ | — | GCP project ID |
| `--location` | ✓ | — | GCP location (e.g. us-central1) |
| `--template-id` | ✓ | — | Template ID to create |
| `--preset` | — | — | Use a preset template: jailbreak |
| `--json` | — | — | JSON body for the template configuration (overrides --preset) |

## Examples

```bash
gws modelarmor +create-template --project P --location us-central1 --template-id my-tmpl --preset jailbreak
gws modelarmor +create-template --project P --location us-central1 --template-id my-tmpl --json '{...}'
```

## Tips

- Defaults to the jailbreak preset if neither --preset nor --json is given.
- Use the resulting template name with +sanitize-prompt and +sanitize-response.

> [!CAUTION]
> This is a **write** command — confirm with the user before executing.

## See Also

- **gws-shared** — Global flags and auth
- [gws-modelarmor](../gws-modelarmor/SKILL.md) — All filter user-generated content for safety commands
