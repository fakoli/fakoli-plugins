---
name: gws-modelarmor-sanitize-response
description: "Google Model Armor: Sanitize a model response through a Model Armor template."
trigger:
  - keyword: sanitize response
  - keyword: modelarmor response
  - keyword: response safety
---

# modelarmor +sanitize-response

> **Note:** See the **gws-shared** skill for auth setup, global flags, and security rules.

Sanitize a model response through a Model Armor template

## Usage

```bash
gws modelarmor +sanitize-response --template <NAME>
```

## Flags

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--template` | ✓ | — | Full template resource name (projects/PROJECT/locations/LOCATION/templates/TEMPLATE) |
| `--text` | — | — | Text content to sanitize |
| `--json` | — | — | Full JSON request body (overrides --text) |

## Examples

```bash
gws modelarmor +sanitize-response --template projects/P/locations/L/templates/T --text 'model output'
model_cmd | gws modelarmor +sanitize-response --template ...
```

## Tips

- Use for outbound safety (model -> user).
- For inbound safety (user -> model), use +sanitize-prompt.

## See Also

- **gws-shared** — Global flags and auth
- [gws-modelarmor](../gws-modelarmor/SKILL.md) — All filter user-generated content for safety commands
