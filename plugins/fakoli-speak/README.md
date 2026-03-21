# fakoli-speak

ElevenLabs text-to-speech for Claude Code with streaming playback and cost tracking.

## Requirements

- **ElevenLabs API key** — set `ELEVENLABS_API_KEY` in `~/.env`
- **Audio player** — `afplay` (macOS, built-in), `mpv`, or `ffplay`
- **Python** >= 3.10
- **uv** for dependency management

## Setup

Add your API key to `~/.env`:

```
ELEVENLABS_API_KEY=sk_your_key_here
```

## Commands

| Command | Description |
|---------|-------------|
| `/speak` | Read the last response aloud |
| `/stop` | Stop current playback |
| `/voices` | List available ElevenLabs voices |
| `/status` | Show playback status and config |
| `/cost` | View usage stats and spending |
| `/autospeak` | Toggle automatic TTS on all responses |

## Configuration

Set these in `~/.env` to customize:

| Variable | Default | Description |
|----------|---------|-------------|
| `ELEVENLABS_API_KEY` | (required) | Your ElevenLabs API key |
| `ELEVENLABS_VOICE_ID` | `21m00Tcm4TlvDq8ikWAM` (Rachel) | Voice to use |
| `ELEVENLABS_MODEL_ID` | `eleven_turbo_v2_5` | TTS model |

Use `/voices` to list available voice IDs.

## Cost Tracking

Every TTS request logs characters used and estimated cost to `~/.claude/fakoli-speak-usage.json`.

```
/cost              # view usage summary
/cost --rate 0.11  # set your plan rate ($/1K chars)
/cost --reset      # reset usage data
/cost --json       # export as JSON
```

Default rate is $0.30/1K characters (Starter plan). Adjust to match your ElevenLabs plan.

## Development

```bash
make install   # install dependencies
make test      # run 56 unit tests
make lint      # check syntax
make clean     # remove build artifacts
```

## License

MIT
