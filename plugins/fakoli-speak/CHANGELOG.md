# Changelog

## [2.1.0] - 2026-09-05

- Add/refresh native Codex manifest and UI metadata while retaining Claude support.
- Add a native skill for the CLI, providers, cost estimates and opt-in autospeak.
- Read current Stop hook last_assistant_message; ignore recursive and malformed events.
- Replace global pkill/bare-PID signaling and CLI-daemon cleanup with an owned persistent playback supervisor.
- Report speech truncation, show active-provider cost overrides, and reject non-finite/negative rates.


## 2.0.2 — 2026-07-04
- Removed unsupported top-level hook metadata from `hooks/hooks.json` so runtime hook loaders accept the autospeak hook configuration.

## 2.0.1 — 2026-06-26
- Fix `/voices` documentation to use the implemented OpenAI voice env var, `OPENAI_TTS_VOICE`.
- Sync release notes with marketplace metadata after the active-plugin audit pass.

## 2.0.0 — 2026-06-26
- Multi-provider TTS release with OpenAI, ElevenLabs, Deepgram, Google Gemini, and macOS Say support.
- Streaming speech, provider selection, voice listing, autospeak, and cost tracking share the Python CLI implementation.

## 1.1.1 — 2026-03-21
- Add LICENSE and CHANGELOG
- Version sync across plugin.json, pyproject.toml, __init__.py

## 1.1.0 — 2026-03-21
- Rewrite as Python CLI with uv (replaced bash script)
- Streaming TTS via ElevenLabs /stream endpoint
- Cost tracking per request with daily/all-time summaries
- Autospeak mode via Stop hook (toggleable)
- Cross-platform audio (afplay/mpv/ffplay)
- Custom exception hierarchy (TTSError, APIKeyMissing, NoPlayerFound, APIError)
- 57 unit tests

## 1.0.0 — 2026-03-21
- Initial release as bash script with ElevenLabs TTS
