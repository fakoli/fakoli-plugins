# Python Style Guide

A reference for Python design philosophy, enforced idioms, and the conventions
a senior Python developer would flag in code review. Sourced from PEP 8, PEP 20,
PEP 544, PEP 557, the Google Python Style Guide, and the Python standard library.

Researched: 2026-04-02
Sources:
- PEP 8: https://peps.python.org/pep-0008/
- PEP 20: https://peps.python.org/pep-0020/
- PEP 544: https://peps.python.org/pep-0544/
- PEP 557: https://peps.python.org/pep-0557/
- Google Python Style Guide: https://google.github.io/styleguide/pyguide.html
- Python docs: https://docs.python.org/3/

---

## Naming Conventions

Source: PEP 8 §Naming Conventions

| Symbol | Convention | Example |
|---|---|---|
| Modules | `snake_case` (short, all lowercase) | `audio_processor`, `voice_registry` |
| Packages | `lowercase` (no underscores preferred) | `fakoli`, `providers` |
| Variables | `snake_case` | `voice_id`, `max_retry_count` |
| Functions / Methods | `snake_case` | `process_audio()`, `list_voices()` |
| Classes | `CapWords` | `AudioProcessor`, `TTSProvider` |
| Type aliases | `CapWords` | `VoiceId`, `AudioFormat` |
| Constants (module-level) | `UPPER_SNAKE_CASE` | `MAX_RETRY_COUNT`, `DEFAULT_RATE` |
| "Protected" members | `_single_leading_underscore` | `_cache`, `_registry` |
| Name-mangled (class-private) | `__double_leading_underscore` | `__secret` (triggers mangling) |
| Magic / dunder methods | `__double_both_sides__` | `__init__`, `__repr__`, `__enter__` |
| Type parameters | `T`, `T_co`, `KT`, `VT` | `T`, `KT`, `VT_co` |

**Never use** `l` (lowercase L), `O` (uppercase O), or `I` (uppercase I) as
single-character variable names — they are indistinguishable from numerals in
many fonts. Use `n`, `idx`, `j` instead.

**Do not invent** `IUser` or `TConfig` prefixes. Python's type system makes the
interface/class distinction clear without notation noise.

---

## Code Layout

Source: PEP 8 §Code Layout

### Indentation

Use **4 spaces** per indentation level. Never tabs. `flake8` and `ruff` enforce
this mechanically — do not debate it.

Continuation lines: align with opening delimiter, or use a hanging indent with
a blank line to separate the continuation from the body.

```python
# Approved — hanging indent, blank line separates arguments from body
def long_function(
    argument_one: str,
    argument_two: int,
    argument_three: float = 1.0,
) -> str:
    return f"{argument_one}: {argument_two}"

# Approved — closing bracket on its own line
result = some_function(
    arg_one,
    arg_two,
    arg_three,
)

# Rejected — continuation line indistinguishable from the body
def long_function(
argument_one, argument_two):
    pass
```

### Line Length

- **79 characters** maximum for code (PEP 8 default).
- **72 characters** maximum for docstrings and comments.
- Teams may negotiate up to **99 characters** if documented in `pyproject.toml`.
- Never allow lines to grow unbounded: a line that requires horizontal scrolling
  is never acceptable.

Prefer breaking at logical boundaries: after a comma, before a binary operator.

```python
# Approved — break before binary operator (PEP 8 updated recommendation)
income = (gross_wages
          + taxable_interest
          + (dividends - qualified_dividends)
          - ira_deduction)

# Rejected — break after operator (old style, harder to read)
income = (gross_wages +
          taxable_interest +
          dividends)
```

### Blank Lines

- **Two** blank lines before and after top-level function and class definitions.
- **One** blank line between methods inside a class.
- **One** blank line sparingly inside functions to group logical steps — never
  more than one, and only where the grouping is non-obvious.

```python
class AudioProcessor:

    def process(self, audio: bytes) -> bytes:
        cleaned = self._remove_silence(audio)
        normalized = self._normalize(cleaned)
        return normalized

    def _remove_silence(self, audio: bytes) -> bytes:
        ...

    def _normalize(self, audio: bytes) -> bytes:
        ...
```

### Trailing Commas

Use trailing commas in multi-line argument lists and collection literals. They
produce cleaner diffs — adding an item changes one line, not two.

```python
# Approved
SUPPORTED_FORMATS = (
    "mp3",
    "opus",
    "aac",
    "flac",
)

# Mandatory for single-element tuples
FILES = ("setup.cfg",)   # Without comma this is just a string in parens
```

---

## Import Ordering

Source: PEP 8 §Imports; Google Style Guide §Imports

Order imports in exactly three groups, each separated by a blank line:

1. **Standard library** — `import os`, `from pathlib import Path`
2. **Third-party packages** — `import httpx`, `from pydantic import BaseModel`
3. **Local / project** — `from .providers import ElevenLabsProvider`

Within each group, sort lexicographically by the full module path.

```python
# Approved — three groups, blank lines between, lexicographic within groups
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from pydantic import BaseModel, Field

from fakoli.providers.base import TTSProvider
from fakoli.registry import ProviderRegistry

if TYPE_CHECKING:
    from fakoli.types import VoiceConfig
```

**Rules:**
- Never use `from module import *` — it makes the namespace unpredictable.
- Use absolute imports; avoid implicit relative imports (`import utils`).
- Explicit relative imports (`from .utils import helper`) are acceptable inside
  a package.
- Put `from __future__ import annotations` first when using PEP 563 deferred
  evaluation. It must be the very first import.
- `TYPE_CHECKING` guard deferred imports to break circular dependencies while
  keeping type information for static analysis.

---

## Whitespace Rules

Source: PEP 8 §Whitespace in Expressions and Statements

```python
# Approved
spam(ham[1], {eggs: 2})
foo = (0,)
bar[1:9], bar[:9], bar[1:]
x = 1
y = 2
long_variable = 3
i = i + 1
c = (a + b) * (a - b)
def munge(input: bytes, sep: bytes | None, limit=1000): ...
ham[1:9:3]  # no spaces around slice colons when all present

# Rejected
spam( ham[ 1], { eggs: 2} )   # spaces inside brackets
bar [1:9 : 3]                  # inconsistent slice spacing
x=1; y=2                       # multiple assignments on one line
def munge(input:bytes,sep:bytes|None,limit = 1000): ...  # missing spaces around annotations
```

No space before `(` in a function call. No space before `[` in indexing.
No space around `=` in keyword arguments **unless** paired with a type annotation.

---

## Quotes

Source: PEP 8 §String Quotes; Google Style Guide §Strings

- Choose single or double quotes and **be consistent** throughout a project.
- Use the opposite quote style to avoid backslash escapes.
- **Triple-quoted strings always use double quotes**: `"""docstring"""`.
- f-strings for interpolation, never string concatenation with `+`.

```python
# Approved
name = "voice"
msg = f"Processing voice: {voice_id}"
doc = """Multi-line docstring."""
inner = "He said 'hello'"   # avoids backslash

# Rejected
msg = "Processing voice: " + voice_id    # string concatenation
msg = "Processing voice: %s" % voice_id  # %-formatting (legacy)
msg = "Processing voice: {}".format(voice_id)  # .format() (acceptable but verbose)
```

**Exception for logging:** Do NOT use f-strings as the first argument to
`logger.*()`. The logger is designed to receive a pattern string and format it
lazily only if the message will actually be emitted. This matters at scale.

```python
# Approved — pattern string, args passed separately
logger.info("Voice %s processed in %dms", voice_id, elapsed_ms)

# Rejected — pre-formats the string even if the log level is suppressed
logger.info(f"Voice {voice_id} processed in {elapsed_ms}ms")
```

---

## The Zen of Python

Source: PEP 20 (`import this`)

The 19 aphorisms. The first five have the most direct implications for code review.

```
Beautiful is better than ugly.
Explicit is better than implicit.
Simple is better than complex.
Complex is better than complicated.
Flat is better than nested.
Sparse is better than dense.
Readability counts.
Special cases aren't special enough to break the rules.
Although practicality beats purity.
Errors should never pass silently.
Unless explicitly silenced.
In the face of ambiguity, refuse the temptation to guess.
There should be one-- and preferably only one --obvious way to do it.
Although that way may not be obvious at first unless you're Dutch.
Now is better than never.
Although never is often better than *right* now.
If the implementation is hard to explain, it's a bad idea.
If the implementation is easy to explain, it may be a good idea.
Namespaces are one honking great idea -- let's do more of those!
```

### "Explicit is better than implicit."

Return types, parameter types, exception types, and default values should all be
stated, not inferred from context.

```python
# Approved — caller knows exactly what this returns and what can go wrong
def get_voice(voice_id: str) -> Voice | None:
    return self._registry.get(voice_id)

# Rejected — caller must read the implementation to know the return type
def get_voice(voice_id):
    return self._registry.get(voice_id)
```

A function that returns `None` implicitly in some branches and a value in others
is a trap. Either always return an expression, or add `return None` explicitly to
every exit path.

```python
# Rejected — None returned implicitly when voice_id not found
def find_voice(voice_id: str) -> str:
    for v in self._voices:
        if v.id == voice_id:
            return v.name

# Approved — all paths explicit
def find_voice(voice_id: str) -> str | None:
    for v in self._voices:
        if v.id == voice_id:
            return v.name
    return None
```

### "Simple is better than complex."

A function that can be described in one sentence should be one function. When you
find yourself writing "and then" in a docstring, it is two functions.

```python
# Rejected — fetches, parses, validates, and persists: four responsibilities
def handle_voice_creation(payload: dict) -> None:
    voice_id = payload.get("id")
    data = requests.post(API_URL, json=payload)
    validated = validate_response(data.json())
    db.insert("voices", validated)
    cache.invalidate(voice_id)

# Approved — each function does exactly one thing
def create_voice(payload: VoicePayload) -> VoiceRecord:
    response = self._client.post("/voices", json=payload)
    return VoiceRecord.from_api_response(response.json())

def persist_voice(record: VoiceRecord) -> None:
    self._db.insert("voices", record.to_dict())
    self._cache.invalidate(record.id)
```

### "Flat is better than nested."

Two levels of nesting is readable. Three is a warning. Four or more is a refactor.
Extract the inner logic into a named helper.

```python
# Rejected — three levels of nesting, guard clause buried
def process_items(items: list[Item]) -> list[Result]:
    results = []
    for item in items:
        if item.is_active:
            for tag in item.tags:
                if tag.startswith("audio"):
                    results.append(transform(item, tag))
    return results

# Approved — early continue (guard clause), flat inner loop
def process_items(items: list[Item]) -> list[Result]:
    results = []
    for item in items:
        if not item.is_active:
            continue
        audio_tags = [t for t in item.tags if t.startswith("audio")]
        results.extend(transform(item, tag) for tag in audio_tags)
    return results
```

### "Errors should never pass silently."

A bare `except:` block is a correctness hole. It catches `KeyboardInterrupt`,
`SystemExit`, `MemoryError`, and programming errors alongside the expected
failure mode. Always name the exception.

```python
# Rejected — catches everything including Ctrl+C and OOM
try:
    result = risky_operation()
except:
    pass

# Rejected — still catches too much, no context preserved
try:
    result = risky_operation()
except Exception:
    pass

# Approved — specific type, context chained, caller informed
try:
    response = self._client.post("/voices", json=payload)
    response.raise_for_status()
except httpx.TimeoutException as exc:
    raise VoiceCreationError(f"Timed out creating voice: {payload!r}") from exc
except httpx.HTTPStatusError as exc:
    raise VoiceCreationError(
        f"API returned {exc.response.status_code}: {exc.response.text}"
    ) from exc
```

---

## Type Annotations

Source: PEP 8 §Type Hints; Google Style Guide §Type Annotations

Type annotations are **required** on all public functions, methods, and class
attributes. Private helpers should be annotated where inference is non-obvious.

```python
# Approved — all signatures fully annotated
class VoiceRegistry:
    _voices: dict[str, VoiceConfig]

    def __init__(self) -> None:
        self._voices = {}

    def register(self, voice_id: str, config: VoiceConfig) -> None:
        self._voices[voice_id] = config

    def get(self, voice_id: str) -> VoiceConfig | None:
        return self._voices.get(voice_id)

    def list_ids(self) -> list[str]:
        return list(self._voices)
```

**Rules:**
- Use `X | Y` (PEP 604, Python 3.10+) not `Union[X, Y]`.
- Use `X | None` not `Optional[X]`.
- Use `list[str]` not `List[str]` (PEP 585, Python 3.9+).
- Use `dict[str, int]` not `Dict[str, int]`.
- Do not annotate `self` or `cls` unless the method returns `Self`.
- Prefer `from __future__ import annotations` at module top to allow forward
  references without quotes.

```python
# Modern (Python 3.10+)
def merge(a: dict[str, int], b: dict[str, int]) -> dict[str, int]: ...

# Legacy — acceptable before Python 3.9
from typing import Dict
def merge(a: Dict[str, int], b: Dict[str, int]) -> Dict[str, int]: ...

# Never
def merge(a, b):  # no annotations at all on public API
    ...
```

### TypeAlias

Name type aliases with `CapWords` and annotate with `TypeAlias` to signal intent.

```python
from typing import TypeAlias

VoiceId: TypeAlias = str
AudioFormat: TypeAlias = str  # "mp3" | "opus" | "aac" | "flac"
JsonPayload: TypeAlias = dict[str, object]
```

---

## Protocols (Structural Subtyping)

Source: PEP 544

A `Protocol` defines an interface by the methods and attributes an object must
have, not by what it inherits from. This is Python's static duck typing.

```python
from typing import Protocol, runtime_checkable

class TTSProvider(Protocol):
    def synthesize(self, text: str, voice_id: str) -> bytes:
        ...

    def list_voices(self) -> list[str]:
        ...
```

Any class that has `synthesize` and `list_voices` with compatible signatures
satisfies `TTSProvider` — no `implements` declaration, no inheritance.

### Protocol vs ABC

| Situation | Use |
|---|---|
| Multiple unrelated implementations, duck typing | `Protocol` |
| Shared default implementation needed | `ABC` |
| Runtime `isinstance()` checks required | `ABC` or `@runtime_checkable Protocol` |
| Third-party classes you cannot modify | `Protocol` |
| Enforcing a contract on your own subclass tree | `ABC` |

### @runtime_checkable

By default, `isinstance(obj, MyProtocol)` raises `TypeError`. Add
`@runtime_checkable` to enable the check — but it only tests for the presence of
methods and attributes, not their signatures.

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Closeable(Protocol):
    def close(self) -> None:
        ...

assert isinstance(open("file.txt"), Closeable)  # True at runtime
```

Use `@runtime_checkable` when you need to branch on capability at runtime (e.g.,
in a plugin registry that detects optional methods). Do not use it as a
substitute for proper type narrowing in typed code.

### Interface Design with Protocols

Keep protocols small — 1 to 5 methods. Compose from smaller protocols.

```python
# Approved — focused, composable protocols
class Synthesizer(Protocol):
    def synthesize(self, text: str, voice_id: str) -> bytes:
        ...

class VoiceManager(Protocol):
    def list_voices(self) -> list[str]:
        ...
    def delete_voice(self, voice_id: str) -> None:
        ...

class StreamingSynthesizer(Synthesizer, Protocol):
    def stream(self, text: str, voice_id: str) -> Iterator[bytes]:
        ...

# Rejected — single protocol that forces all implementations to cover streaming
class TTSProvider(Protocol):
    def synthesize(self, text: str, voice_id: str) -> bytes: ...
    def stream(self, text: str, voice_id: str) -> Iterator[bytes]: ...
    def list_voices(self) -> list[str]: ...
    def delete_voice(self, voice_id: str) -> None: ...
    def clone_voice(self, sample: bytes) -> str: ...
    def get_usage(self) -> UsageStats: ...
```

---

## Dataclasses

Source: PEP 557; `dataclasses` module docs

### Basic Dataclass

```python
from dataclasses import dataclass, field

@dataclass
class VoiceConfig:
    voice_id: str
    model: str = "eleven_multilingual_v2"
    stability: float = 0.5
    similarity_boost: float = 0.75
    tags: list[str] = field(default_factory=list)
```

Generated automatically: `__init__`, `__repr__`, `__eq__`.

### frozen=True for Value Objects

Immutable instances. `__setattr__` and `__delattr__` raise `FrozenInstanceError`.
Use for configuration objects, keys, and any data that should not change after
construction.

```python
@dataclass(frozen=True)
class AudioKey:
    text: str
    voice_id: str
    model: str

    def __hash__(self) -> int:
        # Auto-generated because frozen=True implies eq=True
        # If you define __eq__ manually, you must also define __hash__
        return hash((self.text, self.voice_id, self.model))
```

Because `frozen=True` makes the instance hashable (assuming all fields are
hashable), `AudioKey` can be used as a `dict` key or placed in a `set` — useful
for caches.

### field() for Mutable Defaults

Never use mutable literals as default values. Python raises `ValueError` as of
3.11 for unhashable defaults — catch it before runtime.

```python
# Rejected — raises ValueError at class definition time (Python 3.11+)
@dataclass
class Container:
    items: list[str] = []

# Approved — each instance gets its own list
@dataclass
class Container:
    items: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
```

`field()` parameters:

| Parameter | Type | Default | Purpose |
|---|---|---|---|
| `default` | any | `MISSING` | Scalar default value |
| `default_factory` | `Callable[[], T]` | `MISSING` | Factory for mutable defaults |
| `init` | `bool` | `True` | Include in `__init__` |
| `repr` | `bool` | `True` | Include in `__repr__` |
| `compare` | `bool` | `True` | Include in `__eq__` / `__lt__` etc. |
| `hash` | `bool \| None` | `None` | Include in `__hash__` (None = follow `compare`) |
| `kw_only` | `bool` | `False` | Keyword-only in `__init__` (Python 3.10+) |
| `metadata` | `Mapping` | `None` | Arbitrary annotations for third-party tools |

### __post_init__ Validation

Use `__post_init__` to validate invariants and compute derived fields. It runs
after the generated `__init__`.

```python
@dataclass
class AudioRequest:
    text: str
    voice_id: str
    model: str = "eleven_multilingual_v2"
    _char_count: int = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("text must be non-empty")
        if len(self.text) > 5000:
            raise ValueError(f"text exceeds 5000 characters: {len(self.text)}")
        # Derived field set after validation
        object.__setattr__(self, "_char_count", len(self.text))
        # For frozen dataclasses, use object.__setattr__ to bypass the freeze
```

### InitVar for Init-Only Parameters

`InitVar[T]` fields appear in `__init__` but are not stored as instance
attributes. They are passed to `__post_init__`.

```python
from dataclasses import dataclass, InitVar, field

@dataclass
class VoiceConfigLoader:
    voice_id: str
    config_data: dict[str, object] = field(init=False)
    raw_config: InitVar[dict[str, object]] = None  # type: ignore[assignment]

    def __post_init__(self, raw_config: dict[str, object] | None) -> None:
        self.config_data = raw_config or {}
```

### ClassVar Exclusion

`ClassVar` fields are shared across all instances and excluded from all generated
methods.

```python
from dataclasses import dataclass
from typing import ClassVar

@dataclass
class Provider:
    name: str
    _instance_count: ClassVar[int] = 0  # Not a dataclass field

    def __post_init__(self) -> None:
        Provider._instance_count += 1
```

### KW_ONLY Sentinel (Python 3.10+)

Force all subsequent fields to be keyword-only arguments in `__init__`.

```python
from dataclasses import dataclass, KW_ONLY

@dataclass
class AudioOptions:
    text: str                  # positional
    _: KW_ONLY
    voice_id: str = "default"  # keyword-only
    model: str = "turbo"       # keyword-only

# Usage
opts = AudioOptions("hello", voice_id="nova", model="turbo")
```

---

## Error Handling

Source: PEP 20; PEP 8 §Programming Recommendations; Google Style Guide §Exceptions

### Custom Exception Hierarchies

Every project with more than one error type needs a base exception. Callers can
catch the base to handle all project-specific errors, or catch a subclass to
handle a specific failure mode.

```python
# errors.py — the entire project exception hierarchy in one file


class FakoliError(Exception):
    """Base exception for all Fakoli errors."""


class ProviderError(FakoliError):
    """An error returned by or attributable to a TTS provider."""

    def __init__(self, message: str, provider: str, *, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.provider = provider
        if cause is not None:
            self.__cause__ = cause


class VoiceNotFoundError(ProviderError):
    """Requested voice_id does not exist on the provider."""


class RateLimitError(ProviderError):
    """Provider returned 429; caller should back off and retry."""

    def __init__(self, message: str, provider: str, retry_after_seconds: float) -> None:
        super().__init__(message, provider)
        self.retry_after_seconds = retry_after_seconds


class AuthenticationError(ProviderError):
    """API key missing, expired, or invalid."""
```

### raise ... from exc

Always chain exceptions when translating from one error type to another. This
preserves the full causal chain in tracebacks and logging.

```python
# Approved — original exception is preserved as __cause__
try:
    response = client.post("/v1/text-to-speech", json=payload)
    response.raise_for_status()
except httpx.TimeoutException as exc:
    raise ProviderError(
        f"Request to ElevenLabs timed out after {timeout}s",
        provider="elevenlabs",
    ) from exc
except httpx.HTTPStatusError as exc:
    if exc.response.status_code == 401:
        raise AuthenticationError(
            "ElevenLabs API key is invalid or expired",
            provider="elevenlabs",
        ) from exc
    raise ProviderError(
        f"ElevenLabs returned HTTP {exc.response.status_code}",
        provider="elevenlabs",
    ) from exc

# Rejected — original exception swallowed; traceback loses context
try:
    response = client.post("/v1/text-to-speech", json=payload)
except Exception:
    raise ProviderError("Something went wrong", provider="elevenlabs")
```

Use `from None` only when the original exception is noise and would confuse the
caller (e.g., swallowing an `AttributeError` raised during lazy initialization
that is semantically irrelevant to the caller).

### assert Is Not Validation

`assert` is disabled when Python runs with `-O` (optimized mode). Never use it
for precondition checks in production code.

```python
# Rejected — assert is stripped in optimized mode
def synthesize(text: str, voice_id: str) -> bytes:
    assert text, "text cannot be empty"
    assert len(text) <= 5000, "text too long"

# Approved — raises ValueError, always executed
def synthesize(text: str, voice_id: str) -> bytes:
    if not text:
        raise ValueError("text must be non-empty")
    if len(text) > 5000:
        raise ValueError(f"text must be ≤5000 characters, got {len(text)}")
```

### Minimal try Blocks

Keep the `try` body as small as possible. A large `try` block hides which
statement actually raised, making debugging harder.

```python
# Rejected — three operations under one try; any of them could raise ValueError
try:
    result = compute_something(x)
    other = parse_value(y)
    final = merge(result, other)
except ValueError as exc:
    logger.error("Failed: %s", exc)

# Approved — each exception is clearly attributed
result = compute_something(x)
try:
    other = parse_value(y)
except ValueError as exc:
    raise ConfigError(f"Invalid value in config: {y!r}") from exc
final = merge(result, other)
```

---

## Context Managers

Source: PEP 343; `contextlib` docs

Always use `with` for resources that need cleanup (files, network connections,
locks, temporary state). Never rely on garbage collection.

```python
# Approved — file closed even if body raises
with open(path, "rb") as f:
    data = f.read()

# Rejected — file leaked if read() raises
f = open(path, "rb")
data = f.read()
f.close()
```

### @contextmanager for Simple Context Managers

When a full class is overkill:

```python
from contextlib import contextmanager
from pathlib import Path
import tempfile


@contextmanager
def temp_audio_file(suffix: str = ".mp3"):
    """Yield a temporary file path; delete the file on exit."""
    path = Path(tempfile.mktemp(suffix=suffix))
    try:
        yield path
    finally:
        if path.exists():
            path.unlink()


# Usage
with temp_audio_file(".mp3") as audio_path:
    write_audio(audio_path, data)
    upload(audio_path)
# File deleted here regardless of success or failure
```

### contextlib.suppress for Expected Exceptions

```python
from contextlib import suppress

# Approved — intent is clear: deleting is best-effort
with suppress(FileNotFoundError):
    cache_path.unlink()

# Rejected — try/except with pass obscures whether the silence is intentional
try:
    cache_path.unlink()
except FileNotFoundError:
    pass
```

### contextlib.ExitStack for Dynamic Cleanup

When the number of resources is not known until runtime:

```python
from contextlib import ExitStack

def process_files(paths: list[Path]) -> list[str]:
    with ExitStack() as stack:
        handles = [stack.enter_context(open(p)) for p in paths]
        return [f.read() for f in handles]
    # All files closed here regardless of how many there are
```

---

## pathlib.Path over os.path

Source: PEP 428; Python 3.4+

`pathlib.Path` is the modern, object-oriented path API. Prefer it over `os.path`
for all new code.

| `os.path` (old) | `pathlib` (new) |
|---|---|
| `os.path.join(a, b)` | `Path(a) / b` |
| `os.path.basename(p)` | `Path(p).name` |
| `os.path.dirname(p)` | `Path(p).parent` |
| `os.path.splitext(p)[1]` | `Path(p).suffix` |
| `os.path.exists(p)` | `Path(p).exists()` |
| `os.path.isfile(p)` | `Path(p).is_file()` |
| `os.path.isdir(p)` | `Path(p).is_dir()` |
| `open(p).read()` | `Path(p).read_text(encoding="utf-8")` |
| `open(p, "w").write(s)` | `Path(p).write_text(s, encoding="utf-8")` |
| `os.makedirs(p, exist_ok=True)` | `Path(p).mkdir(parents=True, exist_ok=True)` |
| `glob.glob("**/*.py")` | `Path(".").glob("**/*.py")` |

```python
# Approved
from pathlib import Path

def load_config(config_dir: Path) -> dict:
    config_file = config_dir / "config.json"
    if not config_file.exists():
        raise FileNotFoundError(f"No config at {config_file}")
    return json.loads(config_file.read_text(encoding="utf-8"))

# Rejected
import os, json

def load_config(config_dir):
    config_file = os.path.join(config_dir, "config.json")
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"No config at {config_file}")
    with open(config_file) as f:
        return json.load(f)
```

---

## Collections

Source: `collections` module docs

Use the right collection type for the job. A plain `dict` is often not the right
tool.

### defaultdict — Automatic Missing Keys

```python
from collections import defaultdict

# Count without initializing keys
frequency: defaultdict[str, int] = defaultdict(int)
for word in text.split():
    frequency[word] += 1  # no KeyError on first access

# Group without setdefault
groups: defaultdict[str, list[str]] = defaultdict(list)
for voice_id, category in voice_categories:
    groups[category].append(voice_id)
```

Prefer `defaultdict` over `dict.setdefault()` — the factory is declared once and
applies to every missing key access.

### Counter — Frequency Counting

```python
from collections import Counter

# Count directly from an iterable
word_freq = Counter(text.lower().split())
top_5 = word_freq.most_common(5)

# Multiset arithmetic
a = Counter(["a", "b", "b", "c"])
b = Counter(["b", "b", "b", "d"])
a + b  # Counter({'b': 5, 'a': 1, 'c': 1, 'd': 1})
a & b  # Intersection: Counter({'b': 2})
a - b  # Subtraction (keep positives): Counter({'a': 1, 'c': 1})
```

### deque — Double-Ended Queue

Use `deque` when you need O(1) append or pop from both ends. `list.insert(0, x)`
and `list.pop(0)` are O(n).

```python
from collections import deque

# Bounded queue — automatically drops oldest items
recent_requests: deque[Request] = deque(maxlen=1000)
recent_requests.append(new_request)

# Sliding window
def moving_average(values: Iterable[float], window: int) -> Iterator[float]:
    buf: deque[float] = deque(maxlen=window)
    for v in values:
        buf.append(v)
        if len(buf) == window:
            yield sum(buf) / window
```

### namedtuple — Lightweight Immutable Records

Prefer `@dataclass(frozen=True)` for new code. Use `namedtuple` when you need a
type that is a drop-in replacement for a plain tuple (e.g., returning from a
function that callers may unpack positionally).

```python
from collections import namedtuple

Point = namedtuple("Point", ["x", "y"])
p = Point(3.0, 4.0)
x, y = p           # positional unpacking still works
p.x                # named access
p._asdict()        # {"x": 3.0, "y": 4.0}
p._replace(x=0.0)  # Point(x=0.0, y=4.0)
```

---

## Generators and Lazy Evaluation

### Generator Expressions vs List Comprehensions

Use a generator expression when the result is consumed exactly once and does not
need random access.

```python
# Approved — generator expression: evaluated lazily, O(1) memory
total = sum(item.price for item in cart.items if item.is_taxable)

# Also approved — list comprehension when you need the list itself
names = [user.name for user in active_users]  # needed as a list for sorting

# Rejected — list comprehension fed immediately into sum() is wasteful
total = sum([item.price for item in cart.items if item.is_taxable])
```

### Generator Functions for Streaming

```python
from pathlib import Path


def read_audio_chunks(path: Path, chunk_size: int = 4096) -> Iterator[bytes]:
    """Yield raw audio bytes in fixed-size chunks."""
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            yield chunk
```

### Generator Pipelines

Chain generator functions for memory-efficient, composable data transforms.

```python
def parse_lines(lines: Iterable[str]) -> Iterator[dict]:
    for line in lines:
        yield json.loads(line)

def filter_errors(records: Iterable[dict]) -> Iterator[dict]:
    for record in records:
        if record.get("level") == "error":
            yield record

def format_messages(records: Iterable[dict]) -> Iterator[str]:
    for record in records:
        yield f"[{record['ts']}] {record['message']}"

# Pipeline — no intermediate list is ever materialized
with open("app.log") as f:
    for line in format_messages(filter_errors(parse_lines(f))):
        print(line)
```

---

## functools Patterns

Source: `functools` module docs

### functools.cache

Unbounded memoization. Use for pure functions called repeatedly with the same
arguments, where the argument space is finite and the function is cheap to test
with `cache_info()`.

```python
from functools import cache

@cache
def get_voice_metadata(voice_id: str) -> VoiceMeta:
    """Fetches from API — expensive; cached indefinitely for this process."""
    return api_client.get_voice(voice_id)
```

Arguments must be hashable. Do not apply to functions with side effects, or to
methods bound to an instance (the instance becomes part of the cache key but
prevents garbage collection).

### functools.lru_cache

Bounded LRU memoization. Use when the argument space is large or unbounded and
you need to cap memory usage.

```python
from functools import lru_cache

@lru_cache(maxsize=256)
def load_model_config(model_id: str) -> ModelConfig:
    return ModelConfig.from_file(CONFIG_DIR / f"{model_id}.json")

# Inspect the cache
load_model_config.cache_info()   # CacheInfo(hits=..., misses=..., maxsize=256, currsize=...)
load_model_config.cache_clear()  # Evict all entries
```

### functools.cached_property

Compute a property once per instance, then store it as a plain attribute.

```python
from functools import cached_property

class AudioFile:
    def __init__(self, path: Path) -> None:
        self.path = path

    @cached_property
    def duration_seconds(self) -> float:
        """Expensive: parses audio headers."""
        return _read_audio_duration(self.path)
```

Caveats:
- Not fully thread-safe in Python 3.12+ (per-property lock was removed).
- Does not work with `__slots__` (requires `__dict__`).
- Delete the attribute to force recomputation: `del obj.duration_seconds`.

### functools.partial

Freeze some arguments of a callable to create a specialized version.

```python
from functools import partial

def synthesize(text: str, voice_id: str, model: str, speed: float) -> bytes:
    ...

# Create a preset for this voice and model
nova_synthesize = partial(synthesize, voice_id="nova", model="tts-1", speed=1.0)
audio = nova_synthesize("Hello world")
```

### functools.wraps

Required on every decorator wrapper. Without it, the wrapper replaces the
original function's `__name__`, `__doc__`, and `__module__`.

```python
from functools import wraps
from typing import TypeVar, Callable, ParamSpec

P = ParamSpec("P")
R = TypeVar("R")

def retry(max_attempts: int = 3):
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except TransientError:
                    if attempt == max_attempts - 1:
                        raise
            raise AssertionError("unreachable")
        return wrapper
    return decorator
```

---

## Public API Control

### __all__ in Modules

`__all__` is a list of strings naming the public API of a module. It controls
`from module import *` and is the machine-readable documentation of what is
intentionally public.

```python
# providers/elevenlabs.py

__all__ = [
    "ElevenLabsProvider",
    "ElevenLabsConfig",
]

class ElevenLabsProvider:
    ...

class ElevenLabsConfig:
    ...

def _build_headers(api_key: str) -> dict[str, str]:  # not in __all__, internal
    ...
```

Define `__all__` in every module that is part of a public package. If you omit
it, every name that does not start with `_` is implicitly public — which usually
includes imported names that you did not intend to expose.

### __init__.py Re-export Pattern

The `__init__.py` of a package is its public facade. Import the public API
explicitly and declare `__all__`.

```python
# fakoli/__init__.py

from fakoli.core import synthesize, stream
from fakoli.registry import ProviderRegistry
from fakoli.errors import FakoliError, ProviderError, VoiceNotFoundError
from fakoli.config import FakoliConfig

__all__ = [
    "synthesize",
    "stream",
    "ProviderRegistry",
    "FakoliError",
    "ProviderError",
    "VoiceNotFoundError",
    "FakoliConfig",
]
```

Callers can then use `from fakoli import ProviderRegistry` without knowing that
it lives in `fakoli.registry`. Internal module structure is free to change
without breaking callers.

**Never use `from submodule import *` in `__init__.py`**. It makes the public
API invisible, silently exports internal symbols, and causes surprise on refactor.

```python
# Rejected — what is actually exported? Nobody knows without reading every submodule.
from fakoli.core import *
from fakoli.registry import *
from fakoli.errors import *
```

### Backward Compatibility with __init__.py

When moving a symbol from one module to another, re-export it from the old
location with a deprecation warning to preserve backward compatibility:

```python
# fakoli/old_location.py — symbol moved to fakoli.new_location

import warnings
from fakoli.new_location import NewClass as _NewClass


def OldClass(*args, **kwargs):
    warnings.warn(
        "OldClass has moved to fakoli.new_location.NewClass. "
        "Update your import.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _NewClass(*args, **kwargs)


__all__ = ["OldClass"]
```

---

## pyproject.toml Structure

Source: PEP 518, PEP 621; packaging.python.org

The canonical configuration file for Python projects. All project metadata and
tool configuration lives here.

```toml
[project]
name = "fakoli"
version = "0.3.1"
description = "Multi-provider text-to-speech for Python"
readme = "README.md"
requires-python = ">=3.11"
license = { file = "LICENSE" }
authors = [
    { name = "Sekou Doumbouy", email = "sekou@example.com" },
]
keywords = ["text-to-speech", "tts", "audio"]
classifiers = [
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]
dependencies = [
    "httpx>=0.27",
    "pydantic>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "mypy>=1.9",
    "ruff>=0.4",
]
elevenlabs = ["elevenlabs>=1.0"]
openai = ["openai>=1.0"]

[project.scripts]
fakoli = "fakoli.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "-v --tb=short"

[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = false

[tool.ruff]
line-length = 99
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM"]
ignore = ["E501"]  # line length handled by formatter

[tool.ruff.format]
quote-style = "double"
```

Install dev dependencies: `pip install -e ".[dev]"`.

---

## pytest Conventions

Source: pytest documentation; Real Python pytest guide

### File and Function Naming

- Test files: `test_<module>.py` or `<module>_test.py` (prefer `test_` prefix).
- Test functions: `test_<description>`.
- Test classes: `Test<Subject>` (no `__init__`, no `setUp`).
- Avoid inheriting from `unittest.TestCase` unless migrating legacy code.

### Arrange-Act-Assert Structure

Every test follows this structure. One assertion per logical outcome (not
necessarily one `assert` statement).

```python
def test_synthesize_returns_nonempty_bytes(provider: ElevenLabsProvider) -> None:
    # Arrange
    text = "Hello world"
    voice_id = "nova"

    # Act
    result = provider.synthesize(text, voice_id=voice_id)

    # Assert
    assert isinstance(result, bytes)
    assert len(result) > 0
```

### Fixtures

Fixtures are functions that set up state and optionally tear it down. They are
declared as parameters — pytest injects them automatically.

```python
# conftest.py — fixtures available to all tests in the same directory tree
import pytest
from pathlib import Path


@pytest.fixture
def sample_audio(tmp_path: Path) -> Path:
    """Write a minimal MP3 to a temp file and return the path."""
    path = tmp_path / "sample.mp3"
    path.write_bytes(MINIMAL_MP3_BYTES)
    return path


@pytest.fixture
def mock_provider(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    provider = FakeProvider()
    monkeypatch.setattr("fakoli.registry._default_provider", provider)
    return provider
```

### Fixture Scopes

| Scope | Created | Destroyed | Use for |
|---|---|---|---|
| `function` (default) | Before each test | After each test | Mutable state, tmp files |
| `class` | Before first test in class | After last test in class | Class-level shared state |
| `module` | Before first test in file | After last test in file | Expensive per-file setup |
| `session` | Once per `pytest` run | End of run | DB connections, servers |
| `package` | Once per package | When package finishes | Package-level resources |

```python
@pytest.fixture(scope="session")
def db_connection() -> Iterator[Connection]:
    conn = create_connection(TEST_DATABASE_URL)
    yield conn
    conn.close()
```

### Parametrize

Test multiple inputs without duplicating test bodies.

```python
import pytest

@pytest.mark.parametrize("text,expected_error", [
    ("", "text must be non-empty"),
    ("x" * 5001, "text must be ≤5000 characters"),
    ("   ", "text must be non-empty"),
])
def test_synthesize_rejects_invalid_text(
    text: str,
    expected_error: str,
    provider: ElevenLabsProvider,
) -> None:
    with pytest.raises(ValueError, match=expected_error):
        provider.synthesize(text, voice_id="nova")
```

### Useful Built-in Fixtures

| Fixture | Type | Purpose |
|---|---|---|
| `tmp_path` | `Path` | Temporary directory unique to this test |
| `tmp_path_factory` | `TempPathFactory` | Session-scoped temp directories |
| `monkeypatch` | `MonkeyPatch` | Patch attributes, env vars, dict entries |
| `capsys` | `CaptureFixture` | Capture stdout/stderr |
| `caplog` | `LogCaptureFixture` | Capture log records |
| `request` | `FixtureRequest` | Introspect the test requesting the fixture |

```python
def test_cli_output(capsys: pytest.CaptureFixture[str]) -> None:
    main(["--version"])
    captured = capsys.readouterr()
    assert "0.3.1" in captured.out


def test_reads_env_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKOLI_API_KEY", "test-key-123")
    config = FakoliConfig.from_env()
    assert config.api_key == "test-key-123"
```

---

## Code Review Checklist

A senior reviewer checks these in every Python PR, in priority order.

### Severity Levels

| Level | Meaning | Action |
|---|---|---|
| **MUST** | Correctness, security, or data loss | Block merge |
| **SHOULD** | Clear improvement, well-justified | Fix before merge unless overridden |
| **CONSIDER** | Idiomatic alternative | Author's discretion |
| **NIT** | Minor style issue | Fix if trivial |

### What Every Review Checks

1. **Type annotations.** All public functions and methods fully annotated.
   Missing return type on an exported function is a MUST-fix. `Any` in a public
   API is a MUST-fix.

2. **Exception specificity.** No bare `except:`. No `except Exception: pass`.
   Every `except` clause names a specific type. Every caught exception is either
   re-raised, logged with context, or translated with `raise ... from exc`.

3. **Mutable defaults.** No mutable literal (`[]`, `{}`, `set()`) as a function
   default or dataclass field default without `default_factory`. This is a
   well-known Python footgun and a MUST-fix every time.

4. **Import organization.** Three groups in order: stdlib, third-party, local.
   Blank line between groups. No `from x import *`. Wildcard imports are a
   MUST-fix.

5. **Resource cleanup.** Every `open()`, network connection, or lock acquired
   without a `with` block is a MUST-fix. No cleanup left to garbage collection.

6. **Silent failures.** Any code path that catches and swallows an exception
   without logging or re-raising is a MUST-fix unless it uses `contextlib.suppress`
   with a documented reason.

7. **assert for validation.** Using `assert` to enforce preconditions in
   non-test code is a MUST-fix. Use `if ... raise ValueError`.

8. **__all__ in public modules.** Any module in a public package without `__all__`
   defined is a SHOULD-fix (accidental exports).

9. **Logging with f-strings.** `logger.info(f"...")` is a SHOULD-fix. Use
   `logger.info("...", arg)` pattern.

10. **os.path vs pathlib.** New code using `os.path` when `pathlib.Path` is
    available is a CONSIDER.

### Idiomatic vs Non-Idiomatic Python

| Non-Idiomatic | Idiomatic | Source |
|---|---|---|
| `x == None` | `x is None` | PEP 8 |
| `if len(seq) == 0:` | `if not seq:` | PEP 8 |
| `type(x) == int` | `isinstance(x, int)` | PEP 8 |
| `except:` | `except SpecificError:` | PEP 8, PEP 20 |
| `x = x + 1` in loop | use `+=` | style |
| `"hello " + name` | `f"hello {name}"` | PEP 498 |
| `os.path.join(a, b)` | `Path(a) / b` | PEP 428 |
| `dict[key]` when key may be missing | `dict.get(key)` or `defaultdict` | style |
| `for i in range(len(lst)): lst[i]` | `for item in lst:` | Pythonic |
| `for i, item in enumerate(lst): ...i` | `for i, item in enumerate(lst):` | Pythonic |
| `lambda x: x.name` as a named variable | `def get_name(x): return x.name` | PEP 8 |
| `reduce(lambda a, b: a + b, items)` | `sum(items)` | readability |
| List comprehension fed into `sum()` | Generator expression in `sum()` | efficiency |
| Bare `raise ValueError` from an `except` | `raise ValueError(...) from exc` | PEP 3134 |
| `open(path)` without `with` | `with open(path) as f:` | PEP 343 |
| `items: list = []` in dataclass | `items: list = field(default_factory=list)` | PEP 557 |

---

## What This Guide Approves

- **`from __future__ import annotations`** — deferred annotation evaluation;
  allows forward references and reduces import overhead from `typing`.
- **`@dataclass(frozen=True)`** — immutable value objects with structural
  equality, hashability, and zero boilerplate.
- **`Protocol`** — define interfaces structurally; no inheritance contract
  required from implementors.
- **`pathlib.Path`** — object-oriented paths; eliminates string concatenation
  for filesystem operations.
- **f-strings everywhere except logging calls** — clearest interpolation syntax.
- **`raise X from Y`** — always chain exceptions when translating error types.
- **`contextlib.contextmanager`** — functional context managers without a class.
- **`contextlib.suppress`** — named, intentional exception silencing.
- **Generator expressions in single-use positions** — `sum(x.val for x in items)`.
- **`collections.defaultdict` over `dict.setdefault()`** — factory declared once.
- **`collections.Counter` over manual `dict` counting**.
- **`functools.cache` / `functools.lru_cache`** — pure function memoization.
- **`functools.wraps`** — required on every decorator wrapper.
- **`__all__`** in every public module — explicit, auditable public API surface.
- **`pyproject.toml`** — single configuration file; no `setup.py`, no `setup.cfg`.

## What This Guide Rejects

- **Bare `except:`** — catches `SystemExit`, `KeyboardInterrupt`, `MemoryError`.
  Always a MUST-fix.
- **`assert` for runtime validation** — stripped by `-O`; use `raise ValueError`.
- **Mutable default arguments** — `def f(x=[])` — the list is shared across
  calls. Use `def f(x=None)` with `if x is None: x = []` inside the body, or
  `field(default_factory=list)` in dataclasses.
- **`from module import *`** — namespace pollution; public API becomes invisible.
- **String concatenation for interpolation** — `"hello " + name` — use f-strings.
- **`os.path` for new filesystem code** — use `pathlib.Path`.
- **`type(x) == SomeType` comparisons** — use `isinstance(x, SomeType)`.
- **`x == None` or `x != None`** — use `x is None` / `x is not None`.
- **`if len(seq) == 0`** — use `if not seq`.
- **Named `lambda`** — `f = lambda x: x + 1`. Use `def f(x): return x + 1`.
- **Logging with f-strings** — `logger.info(f"...")`. Use `logger.info("...", arg)`.
- **`raise ExceptionType` without a message** — every exception should have
  enough context for the reader to understand what failed and why.
- **Deep class hierarchies** — more than one level of inheritance is a sign that
  composition or `Protocol` would serve better.
- **`except Exception: pass` without a comment explaining the silence** — silent
  failures hide bugs; `contextlib.suppress` with a documented rationale is the
  approved alternative.
- **`raise` inside `finally`** — suppresses the original exception without
  chaining; this is almost never what you want.
