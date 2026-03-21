#!/bin/bash
# ElevenLabs TTS for Claude Code
# Usage: echo "text" | tts.sh   |   tts.sh "direct text"   |   tts.sh --stop

source ~/.env 2>/dev/null

VOICE_ID="${ELEVENLABS_VOICE_ID:-21m00Tcm4TlvDq8ikWAM}"
MODEL_ID="${ELEVENLABS_MODEL_ID:-eleven_turbo_v2_5}"
MAX_CHARS=4000
PID_FILE="/tmp/claude-tts.pid"

stop_tts() {
  if [ -f "$PID_FILE" ]; then
    kill "$(cat "$PID_FILE")" 2>/dev/null || true
    rm -f "$PID_FILE"
  fi
  pkill -f "afplay /tmp/claude-tts" 2>/dev/null || true
}

if [ "${1:-}" = "--stop" ]; then
  stop_tts
  exit 0
fi

stop_tts

# Read input
if [ -t 0 ] && [ $# -gt 0 ]; then
  TEXT="$*"
else
  TEXT="$(cat)"
fi

[ -z "$TEXT" ] && exit 0

# Truncate
TEXT="${TEXT:0:$MAX_CHARS}"

# Build JSON payload safely with jq
PAYLOAD="$(jq -n \
  --arg text "$TEXT" \
  --arg model "$MODEL_ID" \
  '{
    text: $text,
    model_id: $model,
    voice_settings: { stability: 0.5, similarity_boost: 0.75 }
  }')"

AUDIO_FILE="/tmp/claude-tts-$$.mp3"

HTTP_CODE="$(curl -s -w "%{http_code}" -X POST \
  "https://api.elevenlabs.io/v1/text-to-speech/$VOICE_ID" \
  -H "xi-api-key: $ELEVENLABS_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  --output "$AUDIO_FILE")"

if [ "$HTTP_CODE" = "200" ] && [ -s "$AUDIO_FILE" ]; then
  (
    echo $BASHPID > "$PID_FILE"
    afplay "$AUDIO_FILE" 2>/dev/null
    rm -f "$AUDIO_FILE" "$PID_FILE"
  ) &
else
  rm -f "$AUDIO_FILE"
  exit 1
fi
