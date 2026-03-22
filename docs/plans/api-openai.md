# OpenAI Text-to-Speech API Reference

## Endpoint

```
POST https://api.openai.com/v1/audio/speech
```

## Authentication

Bearer token via `Authorization` header:

```
Authorization: Bearer <OPENAI_API_KEY>
Content-Type: application/json
```

## Request Body (JSON)

| Field | Type | Required | Description |
|---|---|---|---|
| `model` | string | yes | TTS model to use (see Models below) |
| `input` | string | yes | Text to synthesize. Max 4096 characters per request. |
| `voice` | string | yes | Voice to use (see Voices below) |
| `instructions` | string | no | Natural language prompt to guide speech style (tone, accent, emotion). Only effective with `gpt-4o-mini-tts`. |
| `response_format` | string | no | Audio format. Default: `mp3` |
| `speed` | float | no | Playback speed. Range: `0.25` to `4.0`. Default: `1.0` |

## Models

| Model | Notes |
|---|---|
| `gpt-4o-mini-tts` | Recommended. Most expressive, supports `instructions` parameter for style control. |
| `tts-1` | Lower latency, lower quality. Best for real-time/streaming use cases. |
| `tts-1-hd` | Higher quality, higher latency. Best for pre-rendered audio. |

## Voices

All voices support 99+ languages. `gpt-4o-mini-tts` supports all 13. `tts-1` and `tts-1-hd` support the first 9 (alloy through shimmer).

| Voice | Character |
|---|---|
| `alloy` | Neutral and balanced; works as masculine or feminine |
| `ash` | Clear and articulate; expressive, good for style-prompted use |
| `ballad` | Smooth and melodic |
| `coral` | Vibrant and warm; expressive |
| `echo` | Resonant and clear; masculine presentation |
| `fable` | Expressive and warm; masculine presentation |
| `onyx` | Deep and authoritative; masculine presentation |
| `nova` | Bright and energetic; feminine presentation |
| `sage` | Calm and measured; expressive |
| `shimmer` | Bright and cheerful; feminine presentation |
| `verse` | Expressive; style-tunable |
| `marin` | High quality; recommended for `gpt-4o-mini-tts` |
| `cedar` | High quality; recommended for `gpt-4o-mini-tts` |

## Response Formats

| Value | Description |
|---|---|
| `mp3` | Default. Widely compatible. |
| `opus` | Low latency; best for streaming. |
| `aac` | Good compression. |
| `flac` | Lossless. |
| `wav` | Uncompressed PCM in WAV container. |
| `pcm` | Raw 24kHz 16-bit signed little-endian PCM samples, no container. |

The response body is raw audio bytes in the requested format. There is no JSON envelope.

**Response headers to note:**
- `Content-Type`: e.g., `audio/mpeg` for mp3

## Pricing

| Model | Price |
|---|---|
| `tts-1` | $0.015 per 1,000 characters ($15.00 / 1M chars) |
| `tts-1-hd` | $0.030 per 1,000 characters ($30.00 / 1M chars) |
| `gpt-4o-mini-tts` | $0.60 per 1M input characters + $12.00 per 1M output audio tokens |

Billing is per input character, not per second of audio.

## Limits

- **Max input per request:** 4,096 characters
- For longer text, split into chunks and make multiple requests

## httpx Call Reference

```
POST https://api.openai.com/v1/audio/speech
Authorization: Bearer <OPENAI_API_KEY>
Content-Type: application/json

{
  "model": "tts-1",
  "input": "Hello, this is a test.",
  "voice": "alloy",
  "response_format": "mp3",
  "speed": 1.0
}
```

Key httpx parameters:
- `headers={"Authorization": "Bearer <key>", "Content-Type": "application/json"}`
- `json={...}` for the request body
- Use `stream=True` (or httpx streaming) for large responses to avoid buffering the full audio in memory
- Write response bytes directly to file: iterate `response.iter_bytes()`

For `gpt-4o-mini-tts` with style control, add `"instructions": "Speak in a calm, professional tone."` to the body.

## Error Codes

| Status | Meaning |
|---|---|
| 400 | Bad request (invalid parameters) |
| 401 | Invalid or missing API key |
| 429 | Rate limit exceeded |
| 500 | Server error |
