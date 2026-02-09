---
name: configure
description: Set up or update Nano Banana Pro configuration (API key, defaults, agents)
argument: "[setting] - Optional specific setting to configure (e.g., 'api-key', 'model', 'agents')"
---

# Configure Nano Banana Pro

Set up or update the plugin configuration file.

## Steps

### 1. Check for Existing Configuration

Check if `.claude/nano-banana-pro.local.md` already exists in the current project:

```bash
test -f .claude/nano-banana-pro.local.md && echo "EXISTS" || echo "NOT_FOUND"
```

### 2. Create Configuration File (if needed)

If the file does not exist, copy the example template from the plugin:

```bash
mkdir -p .claude
cp "${CLAUDE_PLUGIN_ROOT}/config/nano-banana-pro.example.md" .claude/nano-banana-pro.local.md
```

Then inform the user the file was created and walk them through filling in their settings.

### 3. Configure Settings

Read the current configuration file and walk the user through each section:

1. **API Key** — Ask the user for their Gemini API key
   - Get one at: https://aistudio.google.com/apikey
   - Update the `gemini_api_key` field

2. **Model Selection** — Ask which default model to use
   - `pro` (Gemini 3 Pro) — Advanced reasoning, high-fidelity text
   - `flash` (Gemini 2.5 Flash Image) — Speed and efficiency, low latency

3. **Generation Defaults** — Confirm or update:
   - `default_aspect` — Aspect ratio (1:1, 16:9, 4:3, 9:16, 3:2)
   - `default_size` — Size tier (1K, 2K, 4K, or empty for default)
   - `output_dir` — Where generated images are saved

4. **Optimization** — Configure auto-optimization:
   - `auto_optimize` — Whether to suggest optimization for large images
   - `optimize_preset` — Default preset (github, slack, web, thumbnail)

5. **PaperBanana Agents** — Enable or disable pipeline agents:
   - `agent_retriever` — Context & reference retrieval
   - `agent_planner` — Visual specification planning
   - `agent_stylist` — Aesthetic & style direction
   - `agent_visualizer` — Image generation execution
   - `agent_critic` — Quality evaluation & refinement
   - `critic_max_rounds` — Max refinement iterations (1-3)

### 4. Ensure .gitignore Protection

Check if `.claude/nano-banana-pro.local.md` is in `.gitignore`:

```bash
grep -q "nano-banana-pro.local.md" .gitignore 2>/dev/null && echo "PROTECTED" || echo "NOT_PROTECTED"
```

If not protected, warn the user and offer to add it:

```bash
echo ".claude/nano-banana-pro.local.md" >> .gitignore
```

**WARNING**: The `.local.md` file may contain your API key. Always ensure it is gitignored.

### 5. Show Summary

After configuration, display a summary of all current settings and which agents are enabled/disabled.

## Quick Configuration

If a specific setting argument is provided:

- `api-key` — Jump directly to API key configuration
- `model` — Jump to model selection
- `agents` — Jump to agent enable/disable
- `defaults` — Jump to generation defaults
- `optimize` — Jump to optimization settings

## Documentation

- [Full README](../README.md) — Complete documentation
- [Example Config](../config/nano-banana-pro.example.md) — Template with all settings
