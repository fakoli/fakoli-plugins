# Deepgram Aura Text-to-Speech API Reference

## Endpoint

```
POST https://api.deepgram.com/v1/speak
```

Voice/model is selected via a query parameter, not the request body.

## Authentication

Token-based via `Authorization` header:

```
Authorization: Token <DEEPGRAM_API_KEY>
Content-Type: application/json
```

Alternatively, `Authorization: Bearer <JWT>` is accepted for JWT-based auth.
All requests must be over HTTPS.

## Query Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `model` | string | yes | Voice model identifier. Default: `aura-asteria-en` |
| `encoding` | string | no | Audio encoding. Default: `linear16` |
| `container` | string | no | Audio container. Default: `wav` |
| `sample_rate` | integer | no | Sample rate in Hz. Depends on encoding. |
| `bit_rate` | integer | no | Bit rate in bps. Only applies to `mp3`, `opus`, `aac`. |
| `callback` | string | no | URL for async callback delivery of audio. |
| `callback_method` | string | no | `POST` or `PUT`. Used with `callback`. |

Example URL with query parameters:

```
POST https://api.deepgram.com/v1/speak?model=aura-asteria-en&encoding=mp3
```

## Request Body (JSON)

| Field | Type | Required | Description |
|---|---|---|---|
| `text` | string | yes | Text to synthesize. Max 2,000 characters per request. |

```json
{
  "text": "Hello, this is a test."
}
```

## Response

The response body is raw audio bytes in the requested format. There is no JSON envelope.

**Response headers:**

| Header | Description |
|---|---|
| `Content-Type` | MIME type of the audio (e.g., `audio/mpeg` for mp3) |
| `dg-request-id` | Unique identifier for the request (useful for debugging) |
| `dg-model-name` | Name of the model used |
| `dg-model-uuid` | UUID of the model version used |
| `dg-char-count` | Number of input characters billed |
| `transfer-encoding` | `chunked` — audio streams back as it is generated |

## Audio Format Options

Default output (no format params): `linear16` encoding, `wav` container, 24000 Hz.

| Encoding | Container | Sample Rate (Hz) | Bit Rate (bps) | Content-Type |
|---|---|---|---|---|
| `linear16` | `wav` | 8000, 16000, 24000, 32000, 48000 | N/A | `audio/wav` |
| `linear16` | `none` | 8000, 16000, 24000, 32000, 48000 | N/A | `audio/l16;rate=24000` |
| `mulaw` | `wav` | 8000, 16000 | N/A | `audio/wav` |
| `mulaw` | `none` | 8000, 16000 | N/A | `audio/mulaw;rate=8000` |
| `alaw` | `wav` | 8000, 16000 | N/A | `audio/wav` |
| `alaw` | `none` | 8000, 16000 | N/A | `audio/alaw;rate=8000` |
| `mp3` | N/A | 22050 (fixed) | 32000, 48000 | `audio/mpeg` |
| `opus` | `ogg` | 48000 (fixed) | 4000–650000 | `audio/ogg;codecs=opus` |
| `flac` | N/A | 8000, 16000, 22050, 32000, 48000 | N/A | `audio/flac` |
| `aac` | N/A | 22050 (fixed) | 4000–192000 | `audio/aac` |

Note: If you hear clicks in the audio when using `linear16` raw PCM, add `container=none` to the query string.

## Voices — Aura-1 (English)

12 voices. Identified by `[model]-[voice]-[language]` format. Default: `aura-asteria-en`.

| Model ID | Gender | Accent | Tone / Use Case |
|---|---|---|---|
| `aura-asteria-en` | Feminine | American | Clear, confident, energetic — advertising, IVR |
| `aura-luna-en` | Feminine | American | Friendly, natural, engaging — IVR |
| `aura-stella-en` | Feminine | American | Clear, professional, engaging — customer service |
| `aura-athena-en` | Feminine | British | Calm, smooth, professional — storytelling |
| `aura-hera-en` | Feminine | American | Smooth, warm, professional — informative content |
| `aura-orion-en` | Masculine | American | Approachable, comfortable, calm — informative content |
| `aura-arcas-en` | Masculine | American | Natural, smooth, comfortable — customer service / casual |
| `aura-perseus-en` | Masculine | American | Confident, professional, clear — customer service |
| `aura-angus-en` | Masculine | Irish | Warm, friendly, natural — storytelling |
| `aura-orpheus-en` | Masculine | American | Professional, trustworthy, clear — customer service / storytelling |
| `aura-helios-en` | Masculine | British | Professional, clear, confident — customer service |
| `aura-zeus-en` | Masculine | American | Deep, trustworthy, smooth — IVR |

## Voices — Aura-2 (English, selected)

Aura-2 includes 40+ English voices. Model IDs follow the `aura-2-[voice]-en` pattern. A selection:

| Model ID | Gender | Accent | Tone / Use Case |
|---|---|---|---|
| `aura-2-thalia-en` | Feminine | American | Clear, energetic, enthusiastic — IVR / customer service |
| `aura-2-andromeda-en` | Feminine | American | Casual, expressive — customer service |
| `aura-2-helena-en` | Feminine | American | Caring, friendly, natural — IVR / casual |
| `aura-2-apollo-en` | Masculine | American | Confident, casual — casual chat |
| `aura-2-arcas-en` | Masculine | American | Natural, smooth, comfortable — customer service |
| `aura-2-aries-en` | Masculine | American | Warm, energetic, caring — casual chat |

Aura-2 also supports Spanish (17 voices), Dutch (9), German (7), Italian (10), French (2), and Japanese (5).

## Pricing

| Model | Pay-As-You-Go | Growth Plan |
|---|---|---|
| Aura-2 | $0.030 per 1,000 characters | $0.027 per 1,000 characters |
| Aura-1 | $0.0150 per 1,000 characters | $0.0135 per 1,000 characters |

Billing is per input character as reported in the `dg-char-count` response header.

## Limits

- **Max input per request:** 2,000 characters (Aura-1 and Aura-2)
- **Exceeding character limit:** HTTP 413 response
- **Rate limit exceeded:** HTTP 429 response (concurrency limit reached)
- For longer text, split into chunks and make multiple sequential or concurrent requests within rate limits

## httpx Call Reference

```
POST https://api.deepgram.com/v1/speak?model=aura-asteria-en&encoding=mp3
Authorization: Token <DEEPGRAM_API_KEY>
Content-Type: application/json

{
  "text": "Hello, this is a test."
}
```

Key httpx parameters:
- `params={"model": "aura-asteria-en", "encoding": "mp3"}` for query parameters
- `headers={"Authorization": "Token <key>", "Content-Type": "application/json"}`
- `json={"text": "..."}` for the request body
- Response body is raw audio bytes — read with `response.content` or stream with `response.iter_bytes()`
- Check `response.headers["dg-char-count"]` to verify billing character count

## Error Codes

| Status | Meaning |
|---|---|
| 400 | Bad request (invalid parameters or malformed body) |
| 401 | Invalid or missing API key |
| 413 | Input text exceeds 2,000 character limit |
| 429 | Rate limit / concurrency limit exceeded |
| 500 | Server error |
