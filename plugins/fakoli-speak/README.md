# fakoli-speak

Text-to-speech for Codex and Claude Code using OpenAI, ElevenLabs, Deepgram, Google Gemini, or local macOS speech. Audio is synthesized before playback; streaming provider downloads are buffered by the facade.

## Setup and usage

Install through this repository's marketplace. Requirements: Python 3.10+, `uv`, and an audio player (`afplay`, `mpv`, or `ffplay`). The `macos` provider also needs macOS `say`; cloud providers need their configured API key. The CLI loads `~/.env` without replacing environment variables already set by the caller. Keep keys out of argv, transcripts, and package files.

```bash
uv run --frozen --directory "/path/to/fakoli-speak" fakoli-speak status
uv run --frozen --directory "/path/to/fakoli-speak" fakoli-speak provider
uv run --frozen --directory "/path/to/fakoli-speak" fakoli-speak speak <<'SPEECH'
Read this requested text aloud.
SPEECH
uv run --frozen --directory "/path/to/fakoli-speak" fakoli-speak stop
```

Native Codex exposes the `speak` skill covering speech, playback, provider inspection, voices, usage estimates, and opt-in autospeak. Claude also exposes the seven slash commands. The `provider NAME` command validates and displays that provider; it does not switch the active setting. Set `FAKOLI_SPEAK_PROVIDER` for an invocation or persist it in your own configuration.

## Providers

These are package defaults, not a promise that every account supports every model or voice. Inspect current provider documentation when choosing a new model.

| Provider | Key | Voice/model configuration |
|---|---|---|
| `openai` (default) | `OPENAI_API_KEY` | `OPENAI_TTS_VOICE=nova`, `OPENAI_TTS_MODEL=tts-1` |
| `elevenlabs` | `ELEVENLABS_API_KEY` | `ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM`, `ELEVENLABS_MODEL_ID=eleven_flash_v2_5` |
| `deepgram` | `DEEPGRAM_API_KEY` | `DEEPGRAM_VOICE=aura-asteria-en` |
| `google` | `GEMINI_API_KEY` | `GEMINI_TTS_VOICE=Kore`, `GEMINI_TTS_MODEL=gemini-2.5-flash-preview-tts` |
| `macos` | none | `MACOS_SAY_VOICE=Samantha` |

Use `voices` to inspect a provider's voice list. Google audio is decoded from PCM and wrapped in WAV according to the [speech-generation documentation](https://ai.google.dev/gemini-api/docs/speech-generation). Cloud synthesis sends the requested text to that provider.

## Playback and autospeak

Each request is capped at 4,000 characters or the provider's lower limit; the CLI reports truncation. For longer text, split and sequence requests deliberately—another request stops the recorded previous playback.

A dedicated worker owns each player and removes its temporary audio after playback. Its record is `~/.cache/fakoli-speak/playback.json` (override with `FAKOLI_SPEAK_PID_FILE`). Stop verifies worker identity before signaling; it never broadly kills audio players or trusts a bare PID. The default tracks one active worker per user; concurrent independent invocations should use separate record paths. Playback still depends on audio-device access and the host retaining background processes.

`autospeak on` opts eligible future responses into synthesis; `autospeak off` disables it. The Stop hook reads `last_assistant_message`, ignores recursive/malformed events, and supports older known payload shapes. See [Claude hook inputs](https://code.claude.com/docs/en/hooks). Native Codex also declares the hook, but delivery depends on the host's hook support and trusted definition. Direct skill/CLI invocation is available independently.

## Usage estimates

`cost`, `cost --json`, `cost --rate RATE`, and `cost --reset` manage the local log at `~/.claude/fakoli-speak-usage.json`. Rates are character-based estimates with per-provider overrides. They are not live prices, invoices, or billing telemetry; token/audio-priced models need a suitable estimate. Google's default zero means no character-rate estimate, not a guarantee of free service. The CLI labels estimates accordingly.

## Verification

```bash
uv run --project plugins/fakoli-speak --extra dev pytest plugins/fakoli-speak/tests -q
```

Tests mock provider APIs and use temporary fake players. They check hook extraction, cost overrides, process ownership, cleanup after the calling CLI exits, and shutdown. No paid synthesis, speaker playback, or real credential use is required. Live provider and audio hardware behavior has not been tested by this suite.

MIT licensed.
