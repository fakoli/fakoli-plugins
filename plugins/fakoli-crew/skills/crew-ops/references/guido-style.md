# Guido-Style Python

A reference for the guido agent's coding philosophy, drawn from Guido van Rossum's
public writing, PEP authorship, and decades of Python design decisions.

## PEP 8 — Naming and Layout

Guido authored PEP 8. He enforces it strictly but understands its spirit: consistency
matters more than any individual rule.

### Naming Conventions

| Symbol | Convention | Example |
|---|---|---|
| Modules | `snake_case` | `audio_processor.py` |
| Packages | `snake_case` (short) | `mypackage/` |
| Classes | `PascalCase` | `AudioProcessor` |
| Functions / Methods | `snake_case` | `process_audio()` |
| Constants | `UPPER_CASE` | `MAX_RETRY_COUNT = 3` |
| Private attributes | `_single_leading_underscore` | `self._cache` |
| Name-mangled | `__double_leading` | `self.__internal` (rare) |
| Type variables | `PascalCase` or single cap | `T`, `ReturnType` |

### Line Length and Formatting

PEP 8 says 79 characters. Guido accepts 88–99 in projects that adopted Black or Ruff.
The key principle: a line should fit on a screen without scrolling. If a line wraps, it
should wrap at a logical boundary.

```python
# Guido approves — logical boundary, readable
result = some_function(
    argument_one,
    argument_two,
    keyword=value,
)

# Guido rejects — continuation backslash, fragile
result = some_function(argument_one, argument_two, \
                       keyword=value)
```

## PEP 20 — The Zen of Python

The Zen is Guido's design philosophy compressed into 19 aphorisms. The most consequential
for day-to-day code:

### "Explicit is better than implicit."

```python
# Guido approves — explicit return type, explicit parameter names
def get_user(user_id: int, *, include_deleted: bool = False) -> User | None:
    ...

# Guido rejects — implicit behavior, magic kwargs
def get_user(**kwargs):
    ...
```

### "Simple is better than complex."

```python
# Guido approves — straightforward iteration
names = [user.name for user in users if user.is_active]

# Guido rejects — unnecessary complexity
names = list(map(lambda u: u.name, filter(lambda u: u.is_active, users)))
```

### "Readability counts."

```python
# Guido approves — self-documenting variable names
total_price = sum(item.price for item in cart.items)

# Guido rejects — cryptic abbreviations
tp = sum(i.p for i in c.i)
```

### "Errors should never pass silently."

```python
# Guido approves — specific exception, logged, re-raised or handled
try:
    result = api.fetch(url)
except httpx.TimeoutException as exc:
    logger.warning("Fetch timed out for %s: %s", url, exc)
    raise

# Guido rejects — bare except, silent swallow
try:
    result = api.fetch(url)
except:
    pass
```

### "If the implementation is hard to explain, it's a bad idea."

If you need more than 2 sentences to explain what a function does, it should be
split into smaller functions.

## PEP 544 — Protocols (Structural Subtyping)

Guido championed structural subtyping as the Pythonic alternative to heavy inheritance
hierarchies. Use `Protocol` instead of abstract base classes when you want duck typing
with static type safety.

### When to Use Protocol

- You want to define an interface without forcing inheritance.
- You are integrating with code you do not control.
- You want to support multiple unrelated implementations.

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class ProviderProtocol(Protocol):
    """Any object with these methods is a valid provider."""

    def synthesize(self, text: str, voice_id: str) -> bytes:
        ...

    def list_voices(self) -> list[str]:
        ...

    def stream(self, text: str, voice_id: str) -> Iterator[bytes]:
        ...
```

### Implementing a Protocol (no inheritance needed)

```python
class OpenAIProvider:
    """Implements ProviderProtocol structurally — no explicit inheritance."""

    def synthesize(self, text: str, voice_id: str) -> bytes:
        response = self._client.audio.speech.create(input=text, voice=voice_id)
        return response.content

    def list_voices(self) -> list[str]:
        return ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

    def stream(self, text: str, voice_id: str) -> Iterator[bytes]:
        with self._client.audio.speech.create(..., stream=True) as response:
            yield from response.iter_bytes()
```

### Guido's Protocol Rules

- Protocols should be small — 1 to 5 methods max. Larger protocols are a sign the
  abstraction is wrong.
- Use `@runtime_checkable` when you need `isinstance()` checks at runtime.
- Do NOT use Protocol to recreate Java-style interface hierarchies.

## PEP 557 — Dataclasses

Guido approves of dataclasses as the modern replacement for tuple-heavy data containers
and verbose `__init__` methods.

### Use Dataclasses For

- Plain data containers (configs, request/response models, value objects).
- Objects where the primary purpose is holding data, not behavior.
- Cases where you want automatic `__repr__`, `__eq__`, and optional `__hash__`.

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)  # frozen=True for immutable value objects
class VoiceConfig:
    voice_id: str
    model: str = "tts-1"
    speed: float = 1.0
    output_format: str = "mp3"
    metadata: dict[str, str] = field(default_factory=dict)
```

### Dataclass Patterns Guido Approves

```python
# Post-init validation
@dataclass
class AudioChunk:
    data: bytes
    sample_rate: int
    channels: int = 1

    def __post_init__(self) -> None:
        if self.sample_rate not in (8000, 16000, 22050, 44100, 48000):
            raise ValueError(f"Unsupported sample rate: {self.sample_rate}")
        if len(self.data) == 0:
            raise ValueError("Audio chunk cannot be empty")
```

### What Guido Rejects

```python
# Reject: mutable default — classic bug
@dataclass
class Config:
    tags: list = []  # WRONG — shared across all instances

# Approve: use field(default_factory=...)
@dataclass
class Config:
    tags: list[str] = field(default_factory=list)
```

## Code Review Patterns

Guido's code reviews are methodical. He reads line by line, considers alternatives,
and assigns severity levels.

### Severity Levels

| Level | Meaning | Action Required |
|---|---|---|
| **MUST** | Correctness or security issue | Block merge until fixed |
| **SHOULD** | Clear improvement, good reasons to do it | Fix before merge unless justified |
| **CONSIDER** | Stylistic preference, Pythonic alternative | Author's discretion |
| **NIT** | Minor style issue | Optional; fix if trivial |

### Review Comment Style

```
MUST: This will raise AttributeError if `user` is None.
Add a None check before line 47.

SHOULD: Using a list comprehension here is more readable than the explicit loop.
See lines 23-27.

CONSIDER: This could be a dataclass instead of a plain dict.
Dataclass gives you __repr__ and type safety for free.

NIT: Variable name `d` should be `duration` for readability.
```

### What Guido Always Checks

1. **Type annotations.** Every public function must be annotated. Private helpers
   should be annotated where it aids understanding.
2. **Exception specificity.** No bare `except:`. No `except Exception:` without a
   comment explaining why.
3. **Mutability of defaults.** No mutable default arguments (`def f(x=[]):`).
4. **Import order.** stdlib → third-party → local. One blank line between groups.
5. **`__all__` in public modules.** Defines the public API explicitly.

### Pythonic vs Non-Pythonic

| Non-Pythonic | Pythonic |
|---|---|
| `if len(items) == 0:` | `if not items:` |
| `for i in range(len(items)):` | `for item in items:` or `for i, item in enumerate(items):` |
| `x = None; if cond: x = val` | `x = val if cond else None` |
| `dict.has_key(k)` | `k in dict` |
| `type(x) == int` | `isinstance(x, int)` |
| `lambda x: x.name` | `operator.attrgetter("name")` or a def |
| `try/except` for flow control | Use `if` checks; reserve exceptions for errors |
| `open(f); ... f.close()` | `with open(f) as fh:` |
| Nested ternary `a if x else b if y else c` | Explicit `if/elif/else` block |

## What Guido Approves

- **Short functions.** If a function is more than 20-25 lines, it probably does too much.
- **Descriptive names at module scope, shorter names in tight scopes.**
  `user_authentication_service` at the top; `user` inside a loop.
- **Context managers** for any resource that needs cleanup.
- **Generator expressions** over list comprehensions when only one pass is needed.
- **`pathlib.Path`** over `os.path` string manipulation.
- **f-strings** over `.format()` or `%` formatting.
- **`typing.TypeAlias`** for complex type aliases.
- **`__slots__`** for high-frequency objects where memory matters.

## What Guido Rejects

- **Metaclass magic** for problems that composition or Protocol would solve.
- **`__getattr__` traps** that make attribute access unpredictable.
- **Deep class hierarchies** more than 2 levels deep (prefer composition).
- **`*args, **kwargs` forwarding** without documentation of what is forwarded.
- **Monkey-patching** in production code (acceptable in tests, explicitly marked).
- **Global mutable state** — use dependency injection instead.
- **`assert` for runtime validation** — `assert` is disabled with `-O` flag; use `if/raise`.
- **Catching and re-raising without `raise ... from exc`** (loses the chain).

```python
# Guido rejects — loses exception chain
try:
    result = fetch()
except NetworkError:
    raise ValueError("Could not load data")

# Guido approves — preserves chain
try:
    result = fetch()
except NetworkError as exc:
    raise ValueError("Could not load data") from exc
```
