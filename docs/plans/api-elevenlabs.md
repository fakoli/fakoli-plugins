# ElevenLabs API Reference

Verified against current implementation at
`plugins/fakoli-speak/src/fakoli_speak/tts.py` on 2026-03-21.

---

## Authentication

**Header:** `xi-api-key: <YOUR_API_KEY>`

The implementation uses this header correctly. Retrieve your key from:
https://elevenlabs.io/app/settings/api-keys

---

## Endpoints

### Text-to-Speech (Standard)

```
POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}
```

Returns a complete audio file (not streamed).

---

### Text-to-Speech (Streaming) — used by `speak()`

```
POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream
```

**Status:** URL is correct. The implementation uses this endpoint.

#### Request Headers

| Header          | Value              | Required |
|-----------------|--------------------|----------|
| `xi-api-key`    | Your API key       | Yes      |
| `Content-Type`  | `application/json` | Yes      |

#### Query Parameters

| Parameter                    | Type    | Default | Notes                               |
|------------------------------|---------|---------|-------------------------------------|
| `enable_logging`             | boolean | `true`  |                                     |
| `optimize_streaming_latency` | integer | —       | Values 0–4                          |
| `output_format`              | string  | —       | e.g. `mp3_44100_128`, `pcm_44100`  |

#### Request Body Schema

| Field                    | Type    | Required | Notes                                                |
|--------------------------|---------|----------|------------------------------------------------------|
| `text`                   | string  | Yes      | Text to convert                                      |
| `model_id`               | string  | No       | Default: `eleven_multilingual_v2` (see Models below) |
| `voice_settings`         | object  | No       | See Voice Settings below                             |
| `output_format`          | string  | No       | Audio format override                                |
| `language_code`          | string  | No       | ISO 639-1 code                                       |
| `seed`                   | integer | No       | For deterministic output                             |
| `previous_text`          | string  | No       | Preceding context for prosody continuity             |
| `next_text`              | string  | No       | Following context for prosody continuity             |
| `apply_text_normalization`| string | No       | `"auto"`, `"on"`, or `"off"`                        |

#### Voice Settings Object (`voice_settings`)

| Field               | Type    | Default | Range / Notes                                           |
|---------------------|---------|---------|---------------------------------------------------------|
| `stability`         | float   | ~0.5    | Higher = more consistent/monotone; lower = more expressive |
| `similarity_boost`  | float   | ~0.75   | Higher = closer to original voice; high values amplify audio artifacts |
| `style`             | float   | `0.0`   | Style exaggeration; increases latency when > 0; keep at 0 for stability |
| `speed`             | float   | `1.0`   | Playback speed multiplier; < 1.0 slower, > 1.0 faster  |
| `use_speaker_boost` | boolean | —       | Boosts similarity to original speaker; adds slight latency |

**Current implementation uses only `stability` and `similarity_boost`.**
The `style`, `speed`, and `use_speaker_boost` fields are valid and available
but are not set in `tts.py`. The API will use its defaults for these.

#### Response

- **200 OK:** `application/octet-stream` — binary audio data (MP3 by default)
- **422 Unprocessable Entity:** JSON validation error

---

### Text-to-Speech with Timestamps

```
POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps
POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream/with-timestamps
```

Returns audio with character-level timing data. Not used by current implementation.

---

### List Voices (v1)

```
GET https://api.elevenlabs.io/v1/voices
```

**Status:** URL is correct. The implementation uses this endpoint.

#### Request Headers

| Header       | Value        | Required |
|--------------|--------------|----------|
| `xi-api-key` | Your API key | Yes      |

#### Response Schema

```json
{
  "voices": [
    {
      "voice_id": "string",
      "name": "string",
      "description": "string",
      "category": "premade | cloned | generated | professional | famous | high_quality",
      "labels": {
        "accent": "string",
        "gender": "string",
        "use case": "string",
        "age": "string",
        "descriptive": "string"
      },
      "preview_url": "string",
      "available_for_tiers": ["string"],
      "settings": {
        "stability": 0.0,
        "similarity_boost": 0.0,
        "style": 0.0,
        "speed": 1.0,
        "use_speaker_boost": true
      },
      "sharing": { ... },
      "is_owner": true,
      "is_legacy": false,
      "created_at_unix": 0
    }
  ]
}
```

The implementation accesses `v["labels"]["use case"]` (with a space) which
matches the actual label key format in the API response.

---

### List Voices (v2) — enhanced

```
GET https://api.elevenlabs.io/v2/voices
```

Supports pagination (`next_page_token`, `has_more`, `total_count`), search by
name/description/labels/category, and sorting. The current implementation uses
v1; v2 is preferred for production use with large voice libraries.

---

### Get Voice

```
GET https://api.elevenlabs.io/v1/voices/{voice_id}
```

Returns a single Voice object (same schema as one item in the v1 list response).

---

### Get/Edit Voice Settings

```
GET  https://api.elevenlabs.io/v1/voices/{voice_id}/settings
POST https://api.elevenlabs.io/v1/voices/{voice_id}/settings/edit
GET  https://api.elevenlabs.io/v1/voices/settings/default
```

---

## Available Models

As of 2026-03-21:

| Model ID                    | Status      | Languages | Notes                                                        |
|-----------------------------|-------------|-----------|--------------------------------------------------------------|
| `eleven_v3`                 | Current     | 70+       | Most expressive; dramatic delivery; 5,000 char limit         |
| `eleven_multilingual_v2`    | Current     | 29        | High quality, lifelike; 10,000 char limit; API default       |
| `eleven_flash_v2_5`         | Current     | 32        | Ultra-low latency (~75ms); 40,000 char limit; 50% lower cost |
| `eleven_flash_v2`           | Current     | English   | Ultra-low latency (~75ms); 30,000 char limit; English only   |
| `eleven_turbo_v2_5`         | **Soft-deprecated** | 32 | Functionally equivalent to `eleven_flash_v2_5`; Flash has lower latency |
| `eleven_turbo_v2`           | **Soft-deprecated** | English | Functionally equivalent to `eleven_flash_v2`; Flash preferred |
| `eleven_monolingual_v1`     | Deprecated  | English   | Outclassed by v2 models                                      |
| `eleven_multilingual_v1`    | Deprecated  | 28        | Outclassed by v2 models                                      |
| `eleven_multilingual_sts_v2`| Current     | 29        | Speech-to-Speech (voice changer)                             |
| `eleven_ttv_v3`             | Current     | 70+       | Text-to-Voice design                                         |
| `eleven_text_to_sound_v2`   | Current     | N/A       | Sound effects from text prompts                              |
| `music_v1`                  | Current     | —         | Studio-grade music generation                                |

### DISCREPANCY — Default Model in `tts.py`

The implementation defaults to `eleven_turbo_v2_5` (line 61):

```python
def _get_model_id() -> str:
    return os.environ.get("ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5")
```

`eleven_turbo_v2_5` is soft-deprecated. ElevenLabs documentation states it is
"functionally equivalent" to `eleven_flash_v2_5` but Flash has lower latency.
**Recommendation:** Change default to `eleven_flash_v2_5`.

---

## Default Voice

**Voice name:** Rachel
**Voice ID:** `21m00Tcm4TlvDq8ikWAM`
**Status:** Still active and available as of 2026. Widely referenced in current
ElevenLabs integrations and documentation. The implementation's default is correct.

---

## Pricing (March 2026)

Credit multipliers: for Flash/Turbo v2 and v2.5 models, cost is ~0.5 credits
per character (50% discount vs. standard Multilingual models). As of August 2025,
ElevenLabs unified credit accounting across models.

| Plan      | Monthly Price | Credits/Month  | Overage per 1,000 chars | Notes                                 |
|-----------|---------------|----------------|--------------------------|---------------------------------------|
| Free      | $0            | 10,000         | N/A                      | Non-commercial; 3 custom voices       |
| Starter   | $5            | 30,000         | —                        | Commercial license; instant cloning   |
| Creator   | $22           | 100,000        | $0.30                    | Pro voice cloning; 192 kbps audio     |
| Pro       | $99           | 500,000        | $0.24                    | 44.1 kHz PCM via API                  |
| Scale     | $330          | 2,000,000      | $0.18                    | Multi-seat workspaces                 |
| Business  | $1,320        | 11,000,000     | $0.12                    | Enterprise features                   |

Annual billing gives two months free on all paid plans.

---

## WebSocket API

```
wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input
```

Supports streaming text input (send text in chunks as it becomes available).
Also supports a Multi-Context WebSocket for handling multiple simultaneous
streams. Not used by the current implementation.

---

## Summary of Discrepancies vs. Current Implementation

| # | Location | Issue | Severity |
|---|----------|-------|----------|
| 1 | `tts.py` line 61 | Default model `eleven_turbo_v2_5` is soft-deprecated; prefer `eleven_flash_v2_5` | Low — still works, but Flash has lower latency |
| 2 | `tts.py` line 172 | `voice_settings` only sets `stability` and `similarity_boost`; new fields `style`, `speed`, `use_speaker_boost` are available | Low — API uses safe defaults |
| 3 | `list_voices()` | Uses v1 `/v1/voices` endpoint; v2 `/v2/voices` adds pagination and filtering | Low — v1 still works for small voice lists |
| 4 | N/A | No use of `output_format` query param; defaults to MP3 which is fine for afplay/mpv/ffplay | Informational |

All endpoint URLs (`/v1/text-to-speech/{voice_id}/stream`, `/v1/voices`) and
the auth header (`xi-api-key`) are confirmed correct.
