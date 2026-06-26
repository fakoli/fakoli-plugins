# Changelog

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
