# fakoli-speak

Multi-provider text-to-speech for Claude Code with streaming playback and cost tracking.

Supports **OpenAI TTS**, **ElevenLabs**, **Deepgram Aura**, **Google Gemini**, and **macOS Say**.

## Quick Start

```bash
# Add your preferred provider's API key to ~/.env
OPENAI_API_KEY=sk-your-key-here         # cheapest good option ($0.015/1K chars)

# Set the provider (optional — defaults to openai)
FAKOLI_SPEAK_PROVIDER=openai
```

Then use `/speak` after any Claude response to hear it read aloud.

## Commands

| Command | Description |
|---------|-------------|
| `/speak` | Read the last response aloud |
| `/stop` | Stop current playback |
| `/voices` | List available voices for the active provider |
| `/status` | Show playback status, provider, and config |
| `/cost` | View usage stats and spending |
| `/provider` | Show or switch the active TTS provider |
| `/autospeak` | Toggle automatic TTS on all responses |

## Providers

| Provider | Env Var | Cost/1K chars | Quality |
|----------|---------|---------------|---------|
| **openai** (default) | `OPENAI_API_KEY` | $0.015 | Very good |
| **deepgram** | `DEEPGRAM_API_KEY` | $0.015 | Good |
| **elevenlabs** | `ELEVENLABS_API_KEY` | $0.15–0.30 | Best |
| **google** | `GEMINI_API_KEY` | Free tier | Good |
| **macos** | (none) | Free | Basic |

Switch providers:
```bash
# Add to ~/.env to persist
FAKOLI_SPEAK_PROVIDER=openai

# Or check available providers
/provider
```

## Provider Configuration

Each provider has its own voice and model env vars:

| Variable | Default | Provider |
|----------|---------|----------|
| `OPENAI_TTS_VOICE` | `nova` | openai |
| `OPENAI_TTS_MODEL` | `tts-1` | openai |
| `ELEVENLABS_VOICE_ID` | `21m00Tcm4TlvDq8ikWAM` (Rachel) | elevenlabs |
| `ELEVENLABS_MODEL_ID` | `eleven_flash_v2_5` | elevenlabs |
| `DEEPGRAM_VOICE` | `aura-asteria-en` | deepgram |
| `GEMINI_TTS_VOICE` | `Kore` | google |
| `GEMINI_TTS_MODEL` | `gemini-2.5-flash-preview-tts` | google |
| `MACOS_SAY_VOICE` | `Samantha` | macos |

Use `/voices` to list available voices for the active provider.

## Cost Tracking

Every TTS request logs characters, provider, and estimated cost to `~/.claude/fakoli-speak-usage.json`.

```
/cost              # view usage summary
/cost --rate 0.015 # set your plan rate ($/1K chars)
/cost --reset      # reset usage data
/cost --json       # export as JSON
```

Cost rates are auto-detected per provider. Override with `--rate` if your plan differs.

## Requirements

- **Audio player** — `afplay` (macOS, built-in), `mpv`, or `ffplay`
- **Python** >= 3.10
- **uv** for dependency management
- At least one provider API key in `~/.env` (or use `macos` for free)

## Development

```bash
make install   # install dependencies
make test      # run tests
make lint      # check syntax
make clean     # remove build artifacts
```

## License

MIT

---

Built by [Sekou Doumbouya](https://github.com/fakoli)
