---
# ─── API Key ───────────────────────────────────────────────────
# Get your key at: https://aistudio.google.com/apikey
# IMPORTANT: Never commit this file with a real API key.
# Copy this file to .claude/nano-banana-pro.local.md and add your key.
gemini_api_key: "YOUR_API_KEY_HERE"

# ─── Generation Defaults ──────────────────────────────────────
default_model: "pro"
default_aspect: "1:1"
default_size: ""
output_dir: "./.nanobanana/out"

# ─── Optimization ─────────────────────────────────────────────
auto_optimize: "true"
optimize_preset: "github"

# ─── Remix Settings ───────────────────────────────────────────
max_remix_images: "2"

# ─── PaperBanana Agents ───────────────────────────────────────
# Enable/disable individual agents in the pipeline.
# When disabled, the pipeline skips that agent's phase.
agent_retriever: "true"
agent_planner: "true"
agent_stylist: "true"
agent_visualizer: "true"
agent_critic: "true"

# Maximum critic refinement rounds (1-3)
critic_max_rounds: "3"
---

# Nano Banana Pro Settings

Local configuration for image generation.
See: https://github.com/fakoli/fakoli-plugins/tree/main/plugins/nano-banana-pro#configuration
