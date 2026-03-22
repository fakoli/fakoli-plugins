# Python Agent 3 — Status

**Status: COMPLETE**

---

## Files modified

| File | Action | Summary |
|------|--------|---------|
| `src/fakoli_speak/tts.py` | Replaced | Thin facade over `registry`, `playback`, `cost`; re-exports legacy exceptions and constants |
| `src/fakoli_speak/cost.py` | Replaced | `record_usage` gains `provider` param; provider-scoped `set_cost_rate`; `_get_cost_per_char` resolves via registry; `get_summary` includes `provider` key |
| `src/fakoli_speak/cli.py` | Replaced | Added `cmd_provider` + subparser; updated `cmd_status`, `cmd_voices`, `cmd_cost`; added `registry` import; generic description |
| `commands/provider.md` | Created | New slash-command for `/provider` |
| `commands/speak.md` | Updated | Removed "ElevenLabs" from description |
| `commands/voices.md` | Updated | Removed ElevenLabs-specific text; generic voice env var instructions |
| `commands/cost.md` | Updated | Removed "ElevenLabs" from description |
| `commands/status.md` | Updated | Removed ElevenLabs-specific text |
| `src/fakoli_speak/__init__.py` | Updated | `__version__` bumped to `"2.0.0"` |
| `pyproject.toml` | Updated | version `2.0.0`, multi-provider description |
| `.claude-plugin/plugin.json` | Updated | version `2.0.0`, multi-provider description, expanded keywords |

---

## Design decisions

### tts.py

- Pure delegation layer — imports `playback`, `registry`, `cost` from the package; no `httpx`, no subprocess logic.
- Re-exports `TTSError`, `APIKeyMissing`, `NoPlayerFound`, `APIError` from `protocol.py` so any caller doing `from .tts import TTSError` continues to work.
- Re-exports `PID_FILE` from `playback.py` and defines `MAX_CHARS = 4000` for backward compatibility.
- `speak()` calls `playback.find_player()` before the API call to fail fast if no player is available.
- `speak()` passes `provider=provider.name` to `cost.record_usage` so usage is attributed per provider.

### cost.py

- `record_usage(chars, voice_id, model_id, provider="elevenlabs")` — default preserved for backward compat.
- `_get_cost_per_char(provider_name)` — resolves in order: per-provider override in log → registry default rate → fallback constant.
- `set_cost_rate(cost_per_1k_chars, provider=None)` — when `provider` is `None`, looks up active provider from registry; stores under `cost_per_char_overrides[provider]` key in log JSON.
- `get_summary()` — adds `"provider"` key to returned dict; imports `registry` locally to avoid circular imports.

### cli.py

- `cmd_provider(args)` — shows active provider info or validates a named provider; instructs user to set `FAKOLI_SPEAK_PROVIDER` in `~/.env`.
- `cmd_status` — now prints `Provider:` row with `display_name (name)`.
- `cmd_voices` — prints provider header, uses generic env var instruction.
- `cmd_cost` — header shows `=== TTS Usage (<provider>) ===` instead of hard-coded "ElevenLabs".
- `from . import registry` added to module imports.
- `argparse` description changed to "Multi-provider TTS for Claude Code".

---

## Backward compatibility

- All exceptions (`TTSError`, `APIKeyMissing`, `NoPlayerFound`, `APIError`) importable from `tts.py` as before.
- `tts.PID_FILE` and `tts.MAX_CHARS` still exported.
- `cost.record_usage(chars, voice_id, model_id)` still works (provider defaults to `"elevenlabs"`).
- `cost.set_cost_rate(rate)` still works (provider defaults to active registry provider).
- `cost.get_summary()` returns the same keys as before plus the new `"provider"` key.

---

## What was NOT changed

- `protocol.py` — untouched (owned by Agent 1)
- `playback.py` — untouched (owned by Agent 1)
- `registry.py` — untouched (owned by Agent 1)
- `providers/*.py` — untouched (owned by Agent 2)
- No commits made
