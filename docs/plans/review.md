# Code Review — fakoli-speak v2.0.0

---

## MUST FIX (blocks merge)

### playback.py

- **[playback.py:162] Race condition: PID file written without atomic replace.**
  `PID_FILE.write_text(str(proc.pid))` is not atomic. If two calls to `play_audio()`
  run concurrently (e.g., autospeak fires while a manual `speak` is still launching),
  both processes can write their PIDs in an interleaved window, leaving `stop()` with
  a stale PID. Use `PID_FILE.write_bytes(...)` via a temp-file-then-rename approach,
  or protect the write/read pair with a `threading.Lock`.

- **[playback.py:162] PID file written before cleanup thread is started.**
  If the daemon thread fails to start (extremely rare but possible), the PID file is
  written but never cleaned up, and subsequent `is_playing()` calls will erroneously
  report a live process. Move `PID_FILE.write_text(str(proc.pid))` inside the `try`
  block or, better, after `cleanup.start()`.

- **[playback.py:173] Bare `except Exception` swallows the cause without re-raising
  with context.**
  The bare `raise` on line 180 does preserve the original exception, but this pattern
  is Pythonically weak — it catches `KeyboardInterrupt` subtypes are not `Exception`
  so that is fine, but it also catches `SystemExit`. Narrow to
  `except (OSError, subprocess.SubprocessError)` or add a specific comment justifying
  the broad catch.

- **[playback.py:104-108] `pkill` called unconditionally with no timeout.**
  `subprocess.run(["pkill", ...])` has no `timeout=` argument. On systems where
  `pkill` is absent (e.g., a non-macOS Linux container without procps), this silently
  fails — that part is fine — but without a timeout it can block indefinitely in
  pathological environments. Add `timeout=5`.

### tts.py

- **[tts.py:31-32] `status()` return type is `dict` instead of `dict[str, ...]`.**
  Minor but `dict` without type parameters is the old Python 3.8 style; more
  importantly, if `registry.get_provider()` raises `KeyError` (no providers
  registered, or env var points to missing provider), `status()` will crash with an
  unhandled exception in what callers expect to be a safe read-only query. Add a
  `try/except KeyError` and return a sensible fallback, or document the exception in
  the docstring.

- **[tts.py:31] Missing return type annotation — `dict` is not parameterised.**
  `def status() -> dict:` should be `def status() -> dict[str, object]:` (or a
  TypedDict).  Same applies to `speak() -> dict` and `list_voices() -> list[dict]`.

### cost.py

- **[cost.py:65] Bare `except Exception` in `_get_cost_per_char`.**
  ```python
  except Exception:
      return DEFAULT_COST_PER_CHAR
  ```
  This silently swallows programming errors (e.g., `AttributeError` from a
  mis-implemented provider). At minimum log the exception at DEBUG level so it
  is diagnosable. Use `except (KeyError, AttributeError)` or log before falling
  back.

- **[cost.py:131] Bare `except Exception` in `get_summary`.**
  Same problem as above — swallows all errors from `registry.get_provider()`. Should
  narrow to `except KeyError`.

- **[cost.py:44-46] `_save_log` is not atomic.**
  `COST_LOG_PATH.write_text(json.dumps(...))` replaces the file in-place. If the
  process is killed mid-write, the JSON file is left truncated/corrupt and subsequent
  `_load_log()` calls silently reset to an empty log, losing all history. Write to a
  temp file next to `COST_LOG_PATH` and use `os.replace()` for atomicity.

- **[cost.py:73] Default value `provider: str = "elevenlabs"` is wrong.**
  The `record_usage()` signature defaults `provider` to `"elevenlabs"`, but
  `tts.speak()` always passes an explicit `provider=provider.name`. The misleading
  default means that any caller that forgets the argument will silently record usage
  under the wrong provider. Change the default to `"unknown"` or make the argument
  required (no default).

### registry.py

- **[registry.py:28] `_registry: dict[str, TTSProvider]` is module-level mutable
  state with no thread guard.**
  `register()` and `get_provider()` both mutate/read `_registry` without a lock.
  In a multi-threaded context (unlikely today, but autospeak uses daemon threads),
  a `register()` call racing with a `get_provider()` call during `dict` resize could
  cause a `RuntimeError`. Protect with a `threading.RLock`.

- **[registry.py:129] `discover_providers()` is called at module import time (line
  129).**
  This means that merely importing `fakoli_speak.registry` — e.g., in a test harness
  — triggers network-less side effects (module imports for all providers, including
  the macOS `platform.system()` check, `shutil.which()` calls, etc.). This is a
  design smell but not a hard blocker; however, it does mean that any import error in
  a provider module is suppressed (logged as a warning), which can hide real bugs
  during development. Consider making `discover_providers()` opt-in or called lazily.

### providers/elevenlabs.py

- **[elevenlabs.py:154-176] `APIError` raised inside `httpx.stream()` context manager
  before `resp.read()` is called.**
  On line 172, when `resp.status_code != 200`, `resp.read()` is called to capture
  the body — that is correct. However, the `raise APIError(...)` is inside the `with
  httpx.stream(...) as resp:` block. Because `APIError` is not derived from
  `httpx.HTTPError`, httpx will still close the stream cleanly via the context
  manager's `__exit__`, so this is safe. But the pattern is fragile and non-obvious;
  document it or restructure to read the full response unconditionally when the status
  is not 200.

### providers/google.py

- **[google.py:247-257] `base64.b64decode` can raise `binascii.Error` — not caught.**
  If the API returns malformed base64, `base64.b64decode(b64_audio)` raises
  `binascii.Error` (a subclass of `ValueError`), which is neither caught here nor
  wrapped into `APIError`. Callers will receive an unexpected `binascii.Error`.
  Wrap the decode in a `try/except (ValueError, binascii.Error)` and raise
  `APIError`.

- **[google.py:161-162] Cost rates are hardcoded to 0.0 — inaccurate.**
  Google Gemini TTS is not free for production use beyond the free-tier quota. As of
  the model's knowledge cutoff, `gemini-2.5-flash-preview-tts` is priced per
  character. Hardcoding 0.0 means `get_summary()` will always report $0 for Google,
  which is misleading. Either use real rates or add a comment explicitly documenting
  that this reflects the free-tier assumption with a warning.

### providers/macos.py

- **[macos.py:164-167] Temp output AIFF file is created but immediately closed before
  `say` writes to it — file could be removed by another process.**
  The file is created with `delete=False`, immediately closed (exiting the `with`
  block), and then passed as `-o out_path` to `say`. On macOS this is safe in
  practice, but it is a TOCTOU (time-of-check/time-of-use) anti-pattern. A cleaner
  approach: use `tempfile.mktemp()` (acknowledged unsafe but harmless here) or open
  the file, close it, and document the intent, or use a `TemporaryDirectory`.

- **[macos.py:181-185] `subprocess.run` for `say` has no timeout.**
  For very long texts, `say` can run for minutes. Without a timeout, `synthesize()`
  will block forever if `say` hangs. Add `timeout=300` (or a configurable value).

---

## SHOULD FIX (quality issues)

### protocol.py

- **[protocol.py] No `__all__` defined.**
  `from .protocol import *` would export everything. Define `__all__` to make the
  public API explicit.

- **[protocol.py:75] `@runtime_checkable` protocol — only structural check at runtime.**
  `isinstance(obj, TTSProvider)` only checks for the *existence* of the methods, not
  their signatures. This is a known Python limitation, but worth documenting so
  future maintainers are not surprised when a partially-compliant object passes the
  `isinstance` check.

### playback.py

- **[playback.py:129] `play_audio` return type should be `int` — already correct —
  but the docstring says "returns immediately" without noting the daemon thread
  lifetime.** If the main process exits before the daemon thread finishes, the temp
  file may not be cleaned up. On POSIX, the OS will reclaim it, but this should be
  documented.

- **[playback.py:52] `find_player()` calls `shutil.which()` every time it is called.**
  In a hot path (every `speak()` call), this is an unnecessary repeated filesystem
  scan. Cache the result at module level after the first successful lookup.

### tts.py

- **[tts.py:75] `text = text[:MAX_CHARS]` silently truncates.**
  The caller is not informed of the truncation. Either log a warning or include a
  `truncated: bool` field in the returned dict.

- **[tts.py:61] `speak()` calls `playback.find_player()` as a pre-check (line 73),
  then `playback.stop()` (line 78), then `provider.synthesize()` (line 80), and
  finally `playback.play_audio()` (line 81) which calls `find_player()` again.**
  The double call to `find_player()` is redundant. Either skip the pre-check or pass
  the result through.

### cli.py

- **[cli.py:21] `sys.exit(1)` inside `cmd_speak` — acceptable for a CLI command
  function, but inconsistent with the pattern used everywhere else.**
  All other error conditions are handled by raising `TTSError` and letting `main()`
  catch it and call `sys.exit(1)`. `cmd_speak` should raise `TTSError("No text
  provided.")` instead of calling `sys.exit` directly, to keep the pattern
  consistent and keep the functions unit-testable without `SystemExit`.

- **[cli.py:78] `get_summary()` returns a `provider` key, but `cmd_cost` prints it
  as `s['provider']`.**
  This is fine today, but `get_summary()` returns the *active* provider name, not
  the provider of the historical requests. If the user switches providers between
  runs, the "=== TTS Usage (openai) ===" header may not match the logged entries.
  Consider aggregating by provider in the summary or using a different label.

- **[cli.py:133-134] `load_dotenv` path is hardcoded to `~/.env`.**
  Using `~/.env` is non-standard; most tools use `.env` in the project root.
  This should be documented in the README, and ideally the path should be
  configurable via an env var (e.g., `FAKOLI_DOTENV_PATH`).

- **[cli.py:181-183] No subcommand falls through to `parser.print_help()` +
  `sys.exit(1)` — correct, but `args.command` could also be `None` when `args.func`
  is missing (if a subcommand is added without `set_defaults(func=...)`).** Guard
  with `hasattr(args, "func")` instead of checking `args.command`.

### cost.py

- **[cost.py:12-15] `COST_LOG_PATH` is evaluated at module import time.**
  If `FAKOLI_SPEAK_COST_LOG` is set *after* the module is imported (e.g., in tests),
  the path will not be updated. Make it a function or use `importlib.reload` in tests.
  At minimum document this.

- **[cost.py:148-156] `set_cost_rate` stores the rate as per-character in the log
  but the parameter name is `cost_per_1k_chars`.**
  The division by 1000 (line 155) is correct, but the internal key
  `"cost_per_char_overrides"` stores per-character values while `_get_cost_per_char`
  reads them directly. This is consistent internally but confusing to anyone reading
  the JSON log file. Consider storing per-1k-char values in the log for consistency
  with the `CostRate` dataclass, and adjusting `_get_cost_per_char` accordingly.

### autospeak.py

- **[autospeak.py:28-58] `strip_markdown` has no type annotations on parameters.**
  `def strip_markdown(text: str) -> str:` — the `text` parameter is typed but the
  function signature is present. Actually reading the file: the function *does* have
  `: str` and `-> str`. This is fine. Disregard.

- **[autospeak.py:61] `extract_text_from_hook` has no return type annotation on
  `hook_json` parameter — typed as `dict` without parameterisation.**
  `def extract_text_from_hook(hook_json: dict) -> str | None:` — `dict` should be
  `dict[str, object]` for clarity.

- **[autospeak.py:97-113] `process_hook_stdin` reads all of stdin into memory at once
  with `sys.stdin.read()`.**
  For very large hook payloads this is fine in practice, but if a runaway response
  fills stdin, memory usage is unbounded. Low priority for this use case.

### providers/elevenlabs.py

- **[elevenlabs.py:117] `resp.json().get("voices", [])` — `resp.json()` can raise
  `json.JSONDecodeError` if the server returns a non-JSON body with a 200 status.**
  Wrap in `try/except json.JSONDecodeError` and raise `APIError`.

### providers/openai.py

- **[openai.py:177] `resp.text` in error message could be very large (e.g., HTML
  error page).**
  Truncate to `resp.text[:500]` to avoid flooding logs/stderr.

### providers/deepgram.py

- **[deepgram.py:109-117] `get_cost_rates` deduplication logic is order-dependent.**
  The first model ID per unique rate value is kept. If `_COST_RATES` order changes
  (dict ordering is insertion-order in Python 3.7+, so this is stable), the result
  changes. This is fragile; either return all rates or deduplicate by a stable key
  (e.g., `"aura-1"` and `"aura-2"` sentinel entries).

- **[deepgram.py:175-184] `resp.text` used in error message could be large.**
  Same as openai.py — truncate.

### providers/macos.py

- **[macos.py:48-53] `validate_config` imports `shutil` inside the method.**
  `import shutil` is a stdlib module; just add it to the top-level imports.

- **[macos.py:100] `subprocess.CalledProcessError` caught but `check=True` was
  used.**
  This is correct and intentional. Fine.

- **[macos.py:110] Regex `r"^(.+?)\s{2,}([a-z]{2}_[A-Z]{2,3})\s+#\s*(.*)$"`
  does not handle locale codes longer than 3 uppercase letters.**
  macOS includes voices with locales like `zh_CN`, `pt_BR`, and potentially newer
  locales. `[A-Z]{2,3}` currently allows 2–3 uppercase letters, which covers all
  known cases, but the comment should note this assumption.

---

## NICE TO HAVE

- **`protocol.py`: Add `TypedDict` definitions for the dicts returned by `tts.speak()`,
  `tts.status()`, `tts.list_voices()`, and `cost.record_usage()`.** This would make
  the API self-documenting and enable mypy to catch mismatched key names across the
  codebase (e.g., `cost_usd` vs `cost_per_1k_chars`).

- **`registry.py`: Add a `list_providers()` convenience alias** returning
  `list[TTSProvider]` (not just names), useful for tooling that needs to inspect
  all providers without calling `get_provider()` in a loop.

- **`playback.py`: Consider replacing the daemon-thread cleanup pattern with
  `subprocess.Popen` + a `concurrent.futures.ThreadPoolExecutor`** to prevent
  unbounded thread creation if `play_audio()` is called in rapid succession.

- **`autospeak.py`: `strip_markdown` does not handle setext-style headings**
  (underline with `===` or `---`). The `---` rule is partially handled
  (horizontal rules), but a line of `===` under a heading will pass through as-is.
  Low impact for TTS output.

- **`cost.py`: `record_usage` keeps only the last 100 requests (line 107).** The
  limit is not documented in the public docstring. Add a note.

- **`cli.py`: `cmd_voices` output is formatted with a fixed-width string format
  `{:<25} {:<20} {:<12} {:<10}`.** Long voice IDs (e.g., ElevenLabs UUIDs are 20+
  chars) will overflow the column and misalign the table. Use `textwrap` or dynamic
  column width calculation.

- **All providers: no `__slots__`** — providers are stateless singleton-like objects;
  adding `__slots__` would make this explicit and reduce memory overhead marginally.

- **`providers/google.py`: `_build_wav_header` is a pure function** — consider
  moving it to `playback.py` or a shared `audio_utils.py` module so it can be
  reused if another provider ever returns raw PCM.

- **`autospeak.py`: `MIN_CHARS = 100` is a magic constant** without explanation.
  Add a comment explaining that responses shorter than 100 characters (e.g., "OK" or
  "Done.") are skipped to avoid TTS being triggered by trivial acknowledgements.

---

## IMPORT GRAPH

Tracing all imports to verify the absence of cycles:

```
fakoli_speak/
├── protocol.py
│   └── (stdlib only: dataclasses, typing)
│
├── playback.py
│   └── .protocol  [NoPlayerFound]
│   └── (stdlib: os, shutil, signal, subprocess, tempfile, threading, pathlib)
│
├── registry.py
│   └── .protocol  [TTSProvider]
│   └── fakoli_speak.providers  (lazy, via importlib inside discover_providers())
│   └── (stdlib: importlib, logging, os, pkgutil)
│
├── cost.py
│   └── . registry  (lazy import inside _get_cost_per_char and get_summary)
│   └── (stdlib: json, os, datetime, pathlib)
│
├── tts.py
│   └── . cost
│   └── . playback
│   └── . registry
│   └── .protocol  [APIError, APIKeyMissing, NoPlayerFound, TTSError]
│
├── autospeak.py
│   └── (stdlib: json, re, sys, pathlib)
│
├── cli.py
│   └── . autospeak
│   └── . cost
│   └── . registry
│   └── . tts
│   └── .tts  [TTSError]
│   └── (third-party: dotenv)
│
└── providers/
    ├── __init__.py  (empty docstring only — no imports)
    ├── elevenlabs.py
    │   └── ..protocol  [APIError, APIKeyMissing, CostRate, SpeakResult, Voice]
    │   └── .. registry  [register]
    │   └── (third-party: httpx)
    ├── openai.py
    │   └── ..protocol  [APIError, APIKeyMissing, CostRate, SpeakResult, Voice]
    │   └── .. registry  [register]
    │   └── (third-party: httpx)
    ├── deepgram.py
    │   └── ..protocol  [APIError, APIKeyMissing, CostRate, SpeakResult, Voice]
    │   └── .. registry  [register]
    │   └── (third-party: httpx)
    ├── google.py
    │   └── ..protocol  [APIError, APIKeyMissing, CostRate, SpeakResult, Voice]
    │   └── .. registry  [register]
    │   └── (stdlib: base64, os, struct)
    │   └── (third-party: httpx)
    └── macos.py
        └── ..protocol  [APIError, CostRate, SpeakResult, TTSError, Voice]
        └── .. registry  [register]
        └── (stdlib: os, platform, re, subprocess, tempfile)
```

**Potential circular import risk (NOT a current cycle, but worth monitoring):**

`registry.py` calls `discover_providers()` at module-level (line 129), which imports
every provider module. Each provider module imports `.. registry` (i.e., `registry.py`
itself). Python handles this because by the time each provider module's `from ..
import registry` executes, `registry.py` is already partially initialised (its
top-level `_registry = {}` and `register` function are defined before
`discover_providers()` is called). This is a **load-order dependency** that is
correct today but fragile — if any code is moved above the `_registry = {}` line in
`registry.py`, or if a provider tries to call `get_provider()` at import time, it
will fail with an `AttributeError` or `KeyError`. **Document this invariant
explicitly in `registry.py`.**

No true circular imports exist in the current code. The lazy imports in `cost.py`
(`from . import registry` inside functions) are a correct and intentional design
choice that prevents a `cost → registry → providers → cost` cycle.

---

## PROTOCOL COMPLIANCE

The `TTSProvider` Protocol requires: `name`, `display_name`, `validate_config()`,
`get_voice_id()`, `get_model_id()`, `get_cost_rates()`, `get_default_cost_rate()`,
`list_voices()`, `synthesize()`.

| Provider        | name | display_name | validate_config | get_voice_id | get_model_id | get_cost_rates | get_default_cost_rate | list_voices | synthesize |
|-----------------|------|--------------|-----------------|--------------|--------------|----------------|-----------------------|-------------|------------|
| ElevenLabsProvider | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| OpenAIProvider  | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| DeepgramProvider | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| GoogleProvider  | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| MacOSProvider   | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |

All five providers satisfy the structural protocol. No provider inherits from
`TTSProvider` (correct — structural subtyping, not nominal). An `isinstance(p,
TTSProvider)` check would return `True` for all of them at runtime.

**Note:** `MacOSProvider.validate_config()` raises `TTSError` (not `APIKeyMissing`)
on failure, which is consistent with the protocol docstring ("Raises: APIKeyMissing
if a required environment variable is not set") — since there is no API key, using
`TTSError` is appropriate and arguably more correct. The protocol docstring could be
relaxed to say "Raises: TTSError or a subclass thereof."

---

## BACKWARD COMPATIBILITY CHECK

`tts.py` re-exports:
- `TTSError` — PASS (`from .protocol import ... TTSError`)
- `APIKeyMissing` — PASS
- `NoPlayerFound` — PASS
- `APIError` — PASS
- `PID_FILE` — PASS (`PID_FILE = playback.PID_FILE`)

All five re-exports are present and correct.

---

## VERDICT: FAIL

**Blocking issues:**

1. `playback.py`: Non-atomic PID file write creates a race condition.
2. `playback.py`: `subprocess.run(["pkill", ...])` in `stop()` has no timeout.
3. `cost.py`: `_save_log()` is non-atomic — corrupt JSON on process kill loses all usage history.
4. `cost.py`: `record_usage()` default `provider="elevenlabs"` is misleading and will silently misattribute costs.
5. `providers/google.py`: `base64.b64decode` failure not wrapped in `APIError` — uncaught `binascii.Error` will propagate to the user as an unhandled exception.
6. `cli.py:21`: `sys.exit(1)` inside a library-callable command function breaks unit testability and the established error-handling pattern.

None of these are show-stoppers individually, but items 3, 4, and 5 in particular
will cause silent data corruption or unhandled crashes in normal use. Fix before
merging.
