# Google Gemini TTS API Reference

> **Note:** This uses the Gemini `generateContent` endpoint with `speech_config` — NOT the Google Cloud Text-to-Speech API.

---

## Endpoint

```
POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={API_KEY}
```

**Auth:** API key passed as a URL query parameter (`key=`). No Bearer token needed.

---

## Supported Models

| Model ID | Description |
|---|---|
| `gemini-2.5-flash-preview-tts` | Fast, controllable TTS — low latency, cost-efficient |
| `gemini-2.5-pro-preview-tts` | High-fidelity TTS — optimized for podcasts, audiobooks |

Both models are currently in **Preview** status.

---

## Request Body

### Single-Speaker

```json
{
  "contents": [
    {
      "parts": [{ "text": "Hello, this is a test of the Gemini TTS API." }]
    }
  ],
  "generationConfig": {
    "responseModalities": ["AUDIO"],
    "speechConfig": {
      "voiceConfig": {
        "prebuiltVoiceConfig": {
          "voiceName": "Kore"
        }
      }
    }
  }
}
```

### Multi-Speaker (up to 2 speakers)

The speaker names in `speakerVoiceConfigs` must exactly match the speaker labels used in the prompt text.

```json
{
  "contents": [
    {
      "parts": [
        {
          "text": "Alice: Welcome to the show.\nBob: Thanks for having me!"
        }
      ]
    }
  ],
  "generationConfig": {
    "responseModalities": ["AUDIO"],
    "speechConfig": {
      "multiSpeakerVoiceConfig": {
        "speakerVoiceConfigs": [
          {
            "speaker": "Alice",
            "voiceConfig": {
              "prebuiltVoiceConfig": { "voiceName": "Aoede" }
            }
          },
          {
            "speaker": "Bob",
            "voiceConfig": {
              "prebuiltVoiceConfig": { "voiceName": "Puck" }
            }
          }
        ]
      }
    }
  }
}
```

---

## Response Structure

```json
{
  "candidates": [
    {
      "content": {
        "parts": [
          {
            "inlineData": {
              "data": "<base64-encoded-PCM-audio>",
              "mimeType": "audio/L16;codec=pcm;rate=24000"
            }
          }
        ]
      }
    }
  ]
}
```

**Audio data path:** `candidates[0].content.parts[0].inlineData.data`
**MIME type path:** `candidates[0].content.parts[0].inlineData.mimeType`

---

## Audio Format

| Property | Value |
|---|---|
| Format | Raw PCM (L16) |
| MIME type | `audio/L16;codec=pcm;rate=24000` |
| Sample rate | 24,000 Hz |
| Channels | 1 (mono) |
| Bit depth | 16-bit |

The response returns raw PCM audio. To produce a playable WAV file, add a WAV header or convert with ffmpeg:

```bash
# Decode base64 and convert to WAV using ffmpeg
jq -r '.candidates[0].content.parts[0].inlineData.data' response.json \
  | base64 --decode > audio.pcm

ffmpeg -f s16le -ar 24000 -ac 1 -i audio.pcm output.wav
```

---

## Available Voices (30 total)

| Voice Name | Style |
|---|---|
| Zephyr | Bright |
| Puck | Upbeat |
| Charon | Informative |
| Kore | Firm |
| Fenrir | Excitable |
| Leda | Youthful |
| Orus | Firm |
| Aoede | Breezy |
| Callirrhoe | Easy-going |
| Autonoe | Bright |
| Enceladus | Breathy |
| Iapetus | Clear |
| Umbriel | Easy-going |
| Algieba | Smooth |
| Despina | Smooth |
| Erinome | Clear |
| Algenib | Gravelly |
| Rasalgethi | Informative |
| Laomedeia | Upbeat |
| Achernar | Soft |
| Alnilam | Firm |
| Schedar | Even |
| Gacrux | Mature |
| Pulcherrima | Forward |
| Achird | Friendly |
| Zubenelgenubi | Casual |
| Vindemiatrix | Gentle |
| Sadachbia | Lively |
| Sadaltager | Knowledgeable |
| Sulafat | Warm |

---

## Language Support

Language is **auto-detected** from the input text — no `language_code` parameter is required. Over 70 languages are supported including English, Spanish, French, German, Mandarin (`cmn`), Japanese, Korean, Hindi, and many others via BCP-47 codes.

---

## Limits

| Limit | Value |
|---|---|
| Context window | 32,000 tokens |
| Max speakers (multi-speaker) | 2 |
| Input types | Text only (no audio/image input) |
| Output types | Audio only |

---

## Pricing

### Gemini 2.5 Flash Preview TTS (`gemini-2.5-flash-preview-tts`)

| Tier | Input (text) | Output (audio) |
|---|---|---|
| Free | Free | Free |
| Paid | $0.50 / 1M tokens | $10.00 / 1M tokens |
| Batch (paid) | $0.25 / 1M tokens | $5.00 / 1M tokens |

### Gemini 2.5 Pro Preview TTS (`gemini-2.5-pro-preview-tts`)

| Tier | Input (text) | Output (audio) |
|---|---|---|
| Free | Not available | Not available |
| Paid | $1.00 / 1M tokens | $20.00 / 1M tokens |
| Batch (paid) | $0.50 / 1M tokens | $10.00 / 1M tokens |

---

## curl Example

```bash
curl -s -X POST \
  "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key=${GEMINI_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [{"parts": [{"text": "Hello from Fakoli."}]}],
    "generationConfig": {
      "responseModalities": ["AUDIO"],
      "speechConfig": {
        "voiceConfig": {
          "prebuiltVoiceConfig": {"voiceName": "Kore"}
        }
      }
    }
  }' | jq -r '.candidates[0].content.parts[0].inlineData.data' \
  | base64 --decode > speech.pcm
```

---

## Key Differences from Google Cloud TTS

| | Gemini TTS (this doc) | Google Cloud TTS |
|---|---|---|
| Endpoint | `generativelanguage.googleapis.com` | `texttospeech.googleapis.com` |
| Auth | API key in URL | OAuth2 / Service Account |
| Request field | `generationConfig.speechConfig` | `voice` + `audioConfig` |
| Models | `gemini-2.5-*-preview-tts` | WaveNet, Neural2, Studio, Chirp |
| Output field | `inlineData.data` (base64 PCM) | `audioContent` (base64 MP3/WAV) |

---

*Last updated: 2026-03-21. Model IDs are preview — check [ai.google.dev/gemini-api/docs/speech-generation](https://ai.google.dev/gemini-api/docs/speech-generation) for stable release names.*
