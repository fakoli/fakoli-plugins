---
name: speak
description: Speak requested text through fakoli-speak, inspect TTS providers/voices/playback and estimated cost, or manage its opt-in autospeak setting.
---

# Fakoli Speak

Resolve the plugin root from this installed skill (`../..`) and invoke `uv run --frozen --directory "$PLUGIN_ROOT" fakoli-speak COMMAND`. The CLI loads `~/.env` without overwriting existing environment variables; never print keys. It requires Python, uv, and a supported player (`afplay`, `mpv`, or `ffplay`).

Use `status`, `provider`, `voices`, and `cost --json` to inspect the relevant configuration. The `provider NAME` command validates and displays a provider; it does not persist a switch. Set `FAKOLI_SPEAK_PROVIDER` for the invocation or update the user's configuration only when requested. Read [README](../../README.md) for provider-specific keys and model/voice settings.

For requested speech, pass text through stdin or a structured argv list. Text sent to a cloud provider leaves the machine; use the selected provider and requested text. macOS `say` is local. The current facade caps speech at 4,000 characters (or the provider limit); report `truncated` output instead of claiming the entire text was spoken. If the user needs the full text, split it deliberately and sequence playback, respecting any cost/provider constraints.

`stop` targets only the verified owned playback worker. Do not use broad `pkill` commands or signal an unverified PID. Synthesis completing and playback being launched are different from audible playback being verified. Playback depends on the device/player and session's process lifetime.

Autospeak is opt-in through `autospeak on/off`. Turning it on permits subsequent eligible responses to be sent to the configured provider. The bundled Claude Stop hook uses `last_assistant_message` and ignores recursive/malformed events. Codex can use the skill/CLI directly; hook support and event fields vary by host, so do not promise automatic playback without checking runtime delivery. It does not read arbitrary transcript files.

Costs are local character-based estimates/overrides, not provider invoices; token/audio-priced models and free tiers may differ substantially. Verify provider pricing before a budgeting decision. Never treat a default zero estimate as proof of free usage.
