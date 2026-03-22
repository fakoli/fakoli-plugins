# Python Agent 1 — Status

**Status: COMPLETE**

---

## Files created / modified

| File | Action |
|------|--------|
| `src/fakoli_speak/protocol.py` | Created — exceptions, data classes, `TTSProvider` protocol |
| `src/fakoli_speak/playback.py` | Created — audio playback extracted from `tts.py` |
| `src/fakoli_speak/registry.py` | Replaced — full registry with `get_provider`, `discover_providers` |
| `src/fakoli_speak/providers/__init__.py` | Replaced — empty package marker (was referencing non-existent modules) |
| `docs/plans/agent-python1-status.md` | Created — this file |

---

## Protocol interface (implement against this)

```python
# fakoli_speak/protocol.py

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

class TTSError(Exception): ...
class APIKeyMissing(TTSError): ...
class NoPlayerFound(TTSError): ...
class APIError(TTSError): ...

@dataclass(frozen=True)
class Voice:
    voice_id: str
    name: str
    language: str      # "en", "fr", "multi", ...
    gender: str        # "male", "female", "neutral", "unknown"
    description: str   # free-form

@dataclass(frozen=True)
class CostRate:
    model_id: str
    cost_per_1k_chars: float

@dataclass(frozen=True)
class SpeakResult:
    audio_data: bytes
    audio_format: str  # "mp3", "wav", "aiff", "pcm"
    char_count: int
    voice_id: str
    model_id: str

@runtime_checkable
class TTSProvider(Protocol):
    @property
    def name(self) -> str: ...           # "openai", "elevenlabs", etc.
    @property
    def display_name(self) -> str: ...   # "OpenAI TTS", etc.
    def validate_config(self) -> None: ...  # Raises APIKeyMissing if key missing
    def get_voice_id(self) -> str: ...
    def get_model_id(self) -> str: ...
    def get_cost_rates(self) -> list[CostRate]: ...
    def get_default_cost_rate(self) -> CostRate: ...
    def list_voices(self) -> list[Voice]: ...
    def synthesize(self, text: str) -> SpeakResult: ...
```

---

## playback.play_audio() signature

```python
def play_audio(audio_data: bytes, audio_format: str = "mp3") -> int:
    """Write audio_data to a temp file, launch a player subprocess,
    spawn a daemon cleanup thread, and return the player's PID."""
```

Supporting functions:

```python
PID_FILE: Path  # = Path("/tmp/claude-tts.pid")

def find_player() -> tuple[str, list[str]]: ...   # raises NoPlayerFound
def stop() -> None: ...                            # SIGTERM + pkill patterns
def is_playing() -> tuple[bool, int | None]: ...  # (playing, pid)
```

---

## registry.register() usage pattern

Every provider module should end with:

```python
# src/fakoli_speak/providers/myprovider.py

from fakoli_speak.registry import register

class MyProvider:
    @property
    def name(self) -> str:
        return "myprovider"
    # ... implement all TTSProvider methods ...

register(MyProvider())
```

`registry.discover_providers()` is called automatically at module init via
`pkgutil.iter_modules` over `fakoli_speak/providers/`.  Each discovered module
is imported; import errors are caught and logged as warnings (so a
platform-specific provider failing on the wrong OS does not abort startup).

### Resolution order for `get_provider()`

```
get_provider(name)  # explicit name wins
get_provider()      # falls back to $FAKOLI_SPEAK_PROVIDER, then "openai"
```

```python
from fakoli_speak.registry import get_provider, get_provider_names

provider = get_provider()           # default provider
provider = get_provider("openai")   # explicit
provider = get_provider(None)       # also uses default
names = get_provider_names()        # sorted list of registered names
```
