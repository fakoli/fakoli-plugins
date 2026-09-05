---
description: Configure non-secret Nano Banana Pro defaults and check credential availability
argument-hint: '[model|defaults|api-key|agents|optimize]'
---

Apply the configuration request in `$ARGUMENTS`, preserving existing settings. Read [configuration](../README.md#configuration) for exact discovery and precedence.

For a new setup, create the user configuration without replacing an existing file:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/skills/generate/scripts/nanobanana.py" config --init
```

Use the returned path. Apply only requested changes to its JSON settings. Keep settings outside the plugin installation; relative outputs resolve from the user's working directory. For a legacy project config, either update the explicitly selected file or explain its precedence before migrating it; preserve unrelated fields.

- `model`: `default_model` accepts `pro`, `flash`, or an explicit Gemini model ID.
- `defaults`: set `default_aspect`, `default_size`, `output_dir`, or `max_remix_images` as requested.
- `api-key`: check whether `GEMINI_API_KEY` is available without printing its value. Have the user put a missing key in their environment or `~/.env`; never request a key in chat or save it in plugin files. Do not run a billable generation as a configuration test.
- `agents`: explain that the optional roles can be invoked for suitable tasks; there is no automatic five-agent pipeline. Legacy toggle fields are not runtime switches.
- `optimize`: choose a preset when running `/optimize-image`; optimization is explicit and does not alter future generated files automatically.

A general setup can use the existing defaults immediately. Ask only for a setting whose intended value is missing and materially affects the request. Summarize changed non-secret settings, never credential values.
