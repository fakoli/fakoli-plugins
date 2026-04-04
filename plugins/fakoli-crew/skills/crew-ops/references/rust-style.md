# Rust Style and Convention Guide

A reference for Rust design philosophy, enforced at code review by a senior
Rustacean. Every rule is cited to its authoritative source. Conventions without
citations are community consensus from major production Rust projects.

Researched: 2026-04-02
Primary sources:
- Rust API Guidelines — https://rust-lang.github.io/api-guidelines/
- RFC 430 (Naming Conventions) — https://rust-lang.github.io/rfcs/0430-finalizing-naming-conventions.html
- RFC 1105 (API Evolution) — https://rust-lang.github.io/rfcs/1105-api-evolution.html
- Clippy Documentation — https://doc.rust-lang.org/clippy/

---

## Naming and Casing

Source: RFC 430, Rust API Guidelines §C-CASE

Rust draws a hard line between type-level and value-level constructs. Acronyms
count as one word in both conventions.

### Naming Conventions

| Symbol | Convention | Example | Non-Example |
|---|---|---|---|
| Crates | `snake_case` (single word preferred) | `serde`, `tokio`, `my_crate` | `MyLib`, `my-lib-rs` |
| Modules | `snake_case` | `audio_processor`, `http_client` | `AudioProcessor`, `HttpClient` |
| Types / Structs | `UpperCamelCase` | `AudioChunk`, `ParseError` | `audio_chunk`, `parse_error` |
| Traits | `UpperCamelCase` | `IntoIterator`, `AsRef` | `into_iterator` |
| Enum variants | `UpperCamelCase` | `NotFound`, `InvalidInput` | `not_found`, `INVALID_INPUT` |
| Functions / Methods | `snake_case` | `parse_header()`, `into_bytes()` | `parseHeader()`, `IntoBytes()` |
| Local variables | `snake_case` | `voice_id`, `max_retries` | `voiceId`, `MaxRetries` |
| Constants / Statics | `SCREAMING_SNAKE_CASE` | `MAX_RETRY_COUNT`, `DEFAULT_PORT` | `MaxRetryCount`, `defaultPort` |
| Type parameters | Single uppercase or `UpperCamelCase` | `T`, `K`, `V`, `TItem`, `TError` | `t`, `type_item` |
| Lifetimes | Short lowercase | `'a`, `'buf`, `'static` | `'A`, `'Buf` |

**Acronym rule (RFC 430):** acronyms are one word. In `UpperCamelCase` write
`Uuid`, `HttpClient`, `XmlParser` — never `UUID`, `HTTPClient`, `XMLParser`. In
`snake_case` lowercase the whole acronym: `parse_xml()`, `is_utf8()`.

**Single-letter rule (RFC 430):** in `snake_case`, a single-letter "word" is
only allowed as the final segment. Write `btree_map`, not `b_tree_map`. Write
`PI_2`, not `PI2`.

**Crate naming:** never add `-rs` or `-rust` suffixes. The language is already
implied. Source: API Guidelines §C-CASE.

### Conversion Method Prefixes

Source: API Guidelines §C-CONV

The prefix chosen signals both the cost and the ownership transfer of the
conversion.

| Prefix | Cost | Ownership | Example |
|---|---|---|---|
| `as_` | Free (cast, slice) | borrow → borrow | `str::as_bytes()`, `Path::as_os_str()` |
| `to_` | Potentially expensive | borrow → owned | `str::to_string()`, `f64::to_bits()` |
| `into_` | Variable | owned → owned (consumes) | `String::into_bytes()`, `PathBuf::into_os_string()` |
| `from_` | Conversion constructor | creates from another type | `String::from("hello")` |

`into_inner()` is the standard name for extracting the wrapped value from a
newtype or wrapper (e.g., `Mutex::into_inner()`).

### Getter Naming

Source: API Guidelines §C-GETTER

Omit the `get_` prefix. Name the getter after the field itself.

```rust
// Approved — getter matches field name
impl AudioChunk {
    pub fn sample_rate(&self) -> u32 { self.sample_rate }
    pub fn duration_ms(&self) -> f64 { self.duration_ms }
}

// Rejected — get_ prefix is not idiomatic Rust
impl AudioChunk {
    pub fn get_sample_rate(&self) -> u32 { self.sample_rate }
}
```

Exception: use `get` when the semantics are "index into a collection that may
not contain the key" — e.g., `HashMap::get(&key)`.

### Iterator Method Naming

Source: API Guidelines §C-ITER

Collections that own their data provide three iterator constructors:

```rust
impl AudioBuffer {
    pub fn iter(&self) -> Iter<'_>              { ... } // yields &Sample
    pub fn iter_mut(&mut self) -> IterMut<'_>  { ... } // yields &mut Sample
    pub fn into_iter(self) -> IntoIter          { ... } // yields Sample (via IntoIterator)
}
```

The iterator type names mirror the method names: `Iter`, `IterMut`, `IntoIter`.
Source: API Guidelines §C-ITER-TY.

---

## Type Safety Patterns

Source: API Guidelines §§C-NEWTYPE, C-CUSTOM-TYPE, C-BUILDER

### Newtypes: Distinguish Semantically Different Values

Wrap primitive types in `struct` newtypes to prevent silent unit confusion at
compile time. The cost is zero at runtime.

```rust
// Approved — compiler prevents mixing Hertz and Milliseconds
#[derive(Debug, Clone, Copy, PartialEq, PartialOrd)]
pub struct Hertz(pub f64);

#[derive(Debug, Clone, Copy, PartialEq, PartialOrd)]
pub struct Milliseconds(pub f64);

fn resample(samples: &[f32], from: Hertz, to: Hertz) -> Vec<f32> { ... }

// This would be a type error — cannot pass Milliseconds where Hertz is required
// resample(&buf, Milliseconds(44100.0), Hertz(22050.0));

// Rejected — silent unit confusion is a runtime bug, not a compiler error
fn resample_bad(samples: &[f32], from: f64, to: f64) -> Vec<f32> { ... }
```

Use `#[repr(transparent)]` on newtypes that must have identical memory layout
to their inner type (required for FFI or unsafe code that casts pointers).

```rust
#[repr(transparent)]
pub struct VoiceId(String);
```

Implement `Display`, `From`, and other standard traits by forwarding to the
inner type rather than accessing `.0` throughout the codebase.

### Boolean Arguments: Use Enums

Source: API Guidelines §C-CUSTOM-TYPE

A `bool` argument is a puzzle for the reader at the call site.

```rust
// Rejected — what do true and false mean?
render_widget(widget, true, false);

// Approved — self-documenting at every call site
#[derive(Debug, Clone, Copy)]
pub enum Size { Small, Large }

#[derive(Debug, Clone, Copy)]
pub enum Shape { Round, Square }

render_widget(widget, Size::Small, Shape::Round);
```

### Builders for Complex Construction

Source: API Guidelines §C-BUILDER

When a struct has more than three optional fields, or when construction requires
ordering and validation, introduce a separate builder type.

**Non-consuming builder** (most common): methods return `&mut Self`, allowing
chained configuration and reuse of the same builder.

```rust
#[derive(Default)]
pub struct RequestBuilder {
    url: Option<String>,
    timeout_ms: u64,
    headers: Vec<(String, String)>,
}

impl RequestBuilder {
    pub fn url(&mut self, url: impl Into<String>) -> &mut Self {
        self.url = Some(url.into());
        self
    }
    pub fn timeout_ms(&mut self, ms: u64) -> &mut Self {
        self.timeout_ms = ms;
        self
    }
    pub fn header(&mut self, k: impl Into<String>, v: impl Into<String>) -> &mut Self {
        self.headers.push((k.into(), v.into()));
        self
    }
    pub fn build(self) -> Result<Request, BuildError> {
        let url = self.url.ok_or(BuildError::MissingUrl)?;
        Ok(Request { url, timeout_ms: self.timeout_ms, headers: self.headers })
    }
}

// Call site
let req = RequestBuilder::default()
    .url("https://api.example.com/v1/voices")
    .timeout_ms(5_000)
    .header("Accept", "application/json")
    .build()?;
```

**Consuming builder** (use when the builder holds resources): methods return
`Self`. Necessary when the builder owns file handles or connections.

### Typestate Pattern: Encode Protocol in Types

Encode state machine constraints into the type system so invalid transitions are
compile errors, not runtime panics.

```rust
// States as zero-size types
pub struct Unconnected;
pub struct Connected;
pub struct Authenticated;

pub struct Client<State> {
    inner: ClientInner,
    _state: std::marker::PhantomData<State>,
}

impl Client<Unconnected> {
    pub fn new(addr: &str) -> Self { ... }
    pub fn connect(self) -> Result<Client<Connected>, ConnectError> { ... }
}

impl Client<Connected> {
    pub fn authenticate(self, token: &str) -> Result<Client<Authenticated>, AuthError> { ... }
}

impl Client<Authenticated> {
    pub fn send(&self, msg: &str) -> Result<(), SendError> { ... }
}

// Cannot call send() on Client<Connected> — compiler error
```

---

## Error Handling

### The `thiserror` / `anyhow` Split

This is the most enforced convention in community code review.

| Context | Crate | Reason |
|---|---|---|
| Library crates | `thiserror` | Callers must be able to `match` on specific variants |
| Application / binary crates | `anyhow` | Errors are logged or displayed; type does not matter |
| Internal modules of an app | Either | Prefer `thiserror` for modules others import; `anyhow` at the top level |

```rust
// lib.rs — library: thiserror, named variants, matchable
use thiserror::Error;

#[derive(Debug, Error)]
pub enum VoiceError {
    #[error("voice {id} not found")]
    NotFound { id: String },
    #[error("rate limit exceeded, retry after {retry_after_ms}ms")]
    RateLimited { retry_after_ms: u64 },
    #[error("API error: {0}")]
    Api(#[from] ApiError),
    #[error("I/O error")]
    Io(#[from] std::io::Error),
}
```

```rust
// main.rs — application: anyhow, context chaining, no matching needed
use anyhow::{Context, Result};

fn run() -> Result<()> {
    let config = load_config("config.toml")
        .context("failed to load configuration")?;
    let voice = fetch_voice(&config.voice_id)
        .with_context(|| format!("could not fetch voice {}", config.voice_id))?;
    Ok(())
}
```

**Never use `anyhow` in a library's public API.** Callers lose the ability to
match on specific errors. The `anyhow::Error` type is opaque.

**Error type requirements** (API Guidelines §C-GOOD-ERR):
- Implement `std::error::Error`
- Implement `Send + Sync + 'static` (required by `anyhow` and most async runtimes)
- `Display` message: lowercase, no trailing period, no "Error:" prefix
- Include `#[from]` on the source field rather than writing `From` impls by hand

```rust
// Approved — lowercase, no trailing period
#[error("connection timed out after {timeout_ms}ms")]

// Rejected — capitalized, ends with period
#[error("Connection timed out after {timeout_ms}ms.")]
```

**Never use `()` as an error type.** A `Result<T, ()>` communicates nothing.
Use a concrete type or at minimum `std::convert::Infallible`.

### The `?` Operator and Propagation

Source: API Guidelines §C-QUESTION-MARK

Use `?` at all levels, including in doc examples. Do not use `unwrap()` in
example code — readers copy examples verbatim.

```rust
// Approved in doc examples
/// # Examples
/// ```
/// # fn main() -> Result<(), Box<dyn std::error::Error>> {
/// let voices = client.list_voices()?;
/// # Ok(())
/// # }
/// ```

// Rejected — teaches readers to suppress errors
/// ```
/// let voices = client.list_voices().unwrap();
/// ```
```

### When Panicking Is Acceptable

Panics are appropriate only for programmer errors that represent violated
invariants, not for recoverable runtime conditions.

```rust
// Approved — arithmetic panic signals a programming error in the caller
pub fn sample_at(&self, index: usize) -> f32 {
    assert!(index < self.len(), "index {index} out of bounds (len={})", self.len());
    self.samples[index]
}

// Rejected — network failure is not a programming error
fn fetch_voices() -> Vec<Voice> {
    reqwest::blocking::get(url).unwrap().json().unwrap()
}
```

Document panics in the `# Panics` section of the doc comment
(API Guidelines §C-FAILURE). Document error conditions in `# Errors`.

---

## Documentation Conventions

Source: API Guidelines §§C-CRATE-DOC, C-EXAMPLE, C-FAILURE, C-LINK

### `///` vs `//!`

| Syntax | Use case |
|---|---|
| `///` | Documents the item immediately below (functions, structs, traits, enum variants) |
| `//!` | Documents the containing module or crate (placed at the top of `lib.rs` or `mod.rs`) |

```rust
// lib.rs — crate-level documentation
//! # fakoli-tts
//!
//! Text-to-speech synthesis with multiple provider backends.
//!
//! ## Quick start
//! ```
//! let client = Client::new(Config::from_env()?);
//! let audio = client.synthesize("Hello, world!", "nova").await?;
//! ```

// types.rs — item documentation
/// A unique identifier for a voice model.
///
/// Voice IDs are provider-specific strings. Use [`Client::list_voices`] to
/// enumerate available voices for the configured provider.
///
/// # Examples
/// ```
/// let id = VoiceId::new("nova")?;
/// ```
pub struct VoiceId(String);
```

### What Every Public Item Needs

Source: API Guidelines §C-EXAMPLE

Every public function, method, struct, trait, and enum should have:

1. A one-sentence summary (first line, ends with a period).
2. A blank line, then elaboration if needed.
3. A `# Examples` section with a runnable example.
4. `# Errors` section if the function returns `Result`.
5. `# Panics` section if the function can panic.
6. `# Safety` section (not optional) if the function is `unsafe`.

```rust
/// Synthesizes speech from the given text using the specified voice.
///
/// The returned bytes are PCM audio encoded as 16-bit little-endian samples
/// at the configured sample rate.
///
/// # Errors
///
/// Returns [`VoiceError::NotFound`] if `voice_id` does not exist in the
/// current provider. Returns [`VoiceError::RateLimited`] if the per-minute
/// quota is exceeded.
///
/// # Panics
///
/// Panics if `text` is empty.
///
/// # Examples
///
/// ```
/// # use fakoli_tts::{Client, VoiceId};
/// # async fn example(client: &Client) -> anyhow::Result<()> {
/// let audio = client.synthesize("Hello", "nova").await?;
/// assert!(!audio.is_empty());
/// # Ok(())
/// # }
/// ```
pub async fn synthesize(&self, text: &str, voice_id: &str) -> Result<Vec<u8>, VoiceError> {
```

---

## Standard Trait Implementations

Source: API Guidelines §C-COMMON-TRAITS

Implement standard traits eagerly. Every missing `impl` is a papercut for the
caller. The compiler can derive most of these — no manual implementation needed.

### The Standard Derives Checklist

For any new public type, evaluate each trait in order:

| Trait | When to implement | Derive or manual |
|---|---|---|
| `Debug` | Always | `#[derive(Debug)]` unless the type contains secrets |
| `Clone` | Unless the type is a resource (file, socket) | `#[derive(Clone)]` |
| `Copy` | Only if `Clone` is trivial and the type is small | `#[derive(Copy, Clone)]` — `Copy` requires `Clone` |
| `PartialEq` / `Eq` | When equality comparison makes semantic sense | `#[derive(PartialEq, Eq)]` |
| `PartialOrd` / `Ord` | When ordering makes semantic sense | `#[derive(PartialOrd, Ord)]` |
| `Hash` | When the type will be used as a map key | `#[derive(Hash)]` — requires `Eq` |
| `Default` | When a sensible zero value exists | `#[derive(Default)]` |
| `Display` | When human-readable output is needed | Manual (write the format) |
| `Error` | For all error types | Manual or `#[derive(thiserror::Error)]` |

`PartialEq` and `Eq` must both be derived or both be absent — never one without
the other except for floating-point types.

### From / Into

Source: API Guidelines §C-CONV-TRAITS

Always implement `From`, never `Into`. The blanket impl `impl<T, U: From<T>>
Into<U> for T` provides `Into` automatically.

```rust
// Approved — implement From, get Into for free
impl From<&str> for VoiceId {
    fn from(s: &str) -> Self {
        VoiceId(s.to_owned())
    }
}

// Rejected — redundant, conflicts with blanket impl
impl Into<VoiceId> for &str { ... }
```

Implement `TryFrom` (not `TryInto`) for conversions that can fail.

```rust
impl TryFrom<String> for VoiceId {
    type Error = VoiceIdError;

    fn try_from(s: String) -> Result<Self, Self::Error> {
        if s.trim().is_empty() {
            return Err(VoiceIdError::Empty);
        }
        Ok(VoiceId(s))
    }
}
```

### Display and Error

`Display` for user-facing messages. `Debug` for developer-facing messages. Error
types need both; choose `Display` messages that are lowercase, imperative, and
contain no internal implementation details.

```rust
impl fmt::Display for VoiceId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0)
    }
}
```

### Send + Sync

Source: API Guidelines §C-SEND-SYNC

Types should be `Send + Sync` wherever possible. For types with raw pointers,
verify thread safety with a compile-time assertion:

```rust
// If AudioProcessor is neither Send nor Sync, this will not compile — catch it early
static_assertions::assert_impl_all!(AudioProcessor: Send, Sync);
```

In async code (`tokio`), all types crossing `.await` points must be `Send`.
Prefer returning `impl Future + Send` or use `#[async_trait]` / `trait_variant`
for trait methods that need `Send` bounds.

---

## Generics vs Trait Objects

Source: API Guidelines §C-OBJECT, Effective Rust Item 12

### Decision Table

| Criterion | Generics (`impl Trait` / `T: Trait`) | Trait objects (`dyn Trait`) |
|---|---|---|
| Collection element types | Homogeneous only | Heterogeneous |
| Dispatch cost | Static (monomorphized, inlineable) | Dynamic (vtable lookup, not inlined) |
| Binary size | Grows with each concrete type | Single implementation |
| Trait must be object-safe | Not required | Required |
| Returned from function easily | Yes | Requires `Box<dyn Trait>` |

```rust
// Approved — generic: zero overhead, caller chooses concrete type
pub fn process<R: Read>(reader: R) -> Result<Vec<u8>, io::Error> { ... }

// Approved — trait object: needed when storing mixed types or erasing the concrete type
pub struct ProviderRegistry {
    providers: HashMap<String, Box<dyn TtsProvider + Send + Sync>>,
}

// Rejected — &[&Vec<T>] forces a specific allocation on the caller
pub fn sum_lengths(items: &[&Vec<String>]) -> usize { ... }

// Approved — accept anything that can become an iterator of strings
pub fn sum_lengths<'a>(items: impl IntoIterator<Item = &'a [String]>) -> usize { ... }
```

**Accept the widest input:** prefer `&str` over `&String`, `&[T]` over `&Vec<T>`,
`impl AsRef<Path>` over `&Path`, `impl Into<String>` over `String` in function
arguments. This costs nothing and is strictly more flexible for callers.

Source: API Guidelines §C-GENERIC.

---

## Ownership Patterns

### The Decision Hierarchy

Work through these choices in order. Borrow first; own only when required.

1. **Borrow (`&T`)** — default. Pass a reference unless you need to store the value.
2. **Borrow mutably (`&mut T`)** — when you need to modify but not own.
3. **Clone** — when `&T` would require lifetime annotations that make the API
   awkward, or when the value is small and `Copy`. Make clones visible and
   deliberate, not reflexive.
4. **Move / take ownership** — when the function needs to store the value, or
   the value is consumed by the operation.
5. **`Arc<T>`** — only for shared ownership across threads or when the owner is
   structurally unknown (plugin registry, shared config). Use `Arc::clone(&x)`,
   not `x.clone()`, to signal "this is a reference count bump, not a data copy."

```rust
// Rejected — cloning to satisfy the borrow checker without thought
fn render(&self) -> String {
    let name = self.name.clone(); // unnecessary; name: &str would suffice
    format!("Hello, {}", name)
}

// Approved — borrow the field directly
fn render(&self) -> String {
    format!("Hello, {}", self.name)
}
```

Anti-pattern "clone to satisfy the borrow checker" (Rust Design Patterns): if
a clone makes a borrow error disappear, stop and redesign. The clone is
suppressing a real data dependency, not resolving it.

### Interior Mutability

Use `Cell<T>` for `Copy` types, `RefCell<T>` for non-`Copy` types — both only
in single-threaded code. For multi-threaded contexts, use `Mutex<T>`,
`RwLock<T>`, or an atomic type from `std::sync::atomic`.

Do not hold a `MutexGuard` or `RefCell` borrow across an `.await` point.
This is detected by `clippy::await_holding_lock` and
`clippy::await_holding_refcell_ref`.

---

## Module Structure

### File Layout

```
src/
  lib.rs          ← crate root: re-exports only, no logic
  error.rs        ← all error types for the crate
  types.rs        ← shared value types (newtypes, enums)
  provider/
    mod.rs        ← re-exports Provider trait and built-in impls
    trait.rs      ← the Provider trait definition
    elevenlabs.rs ← ElevenLabs implementation
    openai.rs     ← OpenAI implementation
  client.rs       ← public Client struct
tests/
  integration.rs  ← tests that use the public API only
```

### The `mod.rs` / File Module Choice

From Rust edition 2018 onward, `foo/mod.rs` and `foo.rs` (with a `foo/`
subdirectory for children) are both valid. Prefer `mod.rs` when a module has
children — it keeps the module and its children as an atomic unit in the
filesystem.

**Never place logic in `lib.rs`.** `lib.rs` is a table of contents. All
definitions live in topically named files; `lib.rs` re-exports the public API.

```rust
// lib.rs — Approved: pure re-exports
pub use client::Client;
pub use error::Error;
pub use types::{AudioFormat, VoiceId};

pub mod provider;

mod client;
mod error;
mod types;
```

### Re-export Patterns

Public API lives in `lib.rs` re-exports. Internal modules are `pub(crate)` or
`pub(super)`, never `pub`.

```rust
// Approved — explicit, auditable public surface
pub use self::client::Client;
pub use self::error::{Error, ErrorKind};
pub use self::voice::{Voice, VoiceId};

// Rejected — glob exports make the public surface invisible
pub use self::client::*;
```

---

## Clippy Configuration

Clippy has several groups. The minimum CI configuration enforces the defaults
and the most impactful restriction-group lints.

### Configuring Clippy in Source

Place these at the top of `lib.rs` or `main.rs`. Do not scatter lint attributes
throughout the codebase.

```rust
// At the crate root — the recommended production baseline
#![deny(clippy::all)]                    // default set, no false positives
#![warn(clippy::pedantic)]               // opinionated; expect to allow some
#![warn(clippy::nursery)]                // experimental; review before enabling

// Restriction lints — cherry-pick, never enable the whole group
#![warn(clippy::unwrap_used)]            // use ? or .expect("reason")
#![warn(clippy::expect_used)]            // .expect() is ok if msg explains invariant
#![warn(clippy::panic)]                  // explicit panics in library code
#![warn(clippy::indexing_slicing)]       // use .get() and check bounds
#![warn(clippy::missing_errors_doc)]     // # Errors section required
#![warn(clippy::missing_panics_doc)]     // # Panics section required
```

### CI Command

```bash
# Treat all warnings as errors in CI
cargo clippy -- -D warnings
```

### The Most Impactful Clippy Lints

| Lint | Group | What it catches |
|---|---|---|
| `unwrap_used` | restriction | `.unwrap()` on `Option`/`Result` — use `?` or `.expect()` |
| `expect_used` | restriction | `.expect()` without a meaningful message |
| `panic` | restriction | `panic!()` in library code |
| `indexing_slicing` | restriction | `vec[i]` without bounds check — use `.get(i)` |
| `cast_possible_truncation` | pedantic | `x as u8` when `x: u32` — use `u8::try_from(x)?` |
| `cast_lossless` | pedantic | `x as i32` when `x: u8` — use `i32::from(x)` |
| `must_use_candidate` | pedantic | Functions returning non-trivial values should be `#[must_use]` |
| `missing_errors_doc` | pedantic | `Result`-returning functions missing `# Errors` |
| `missing_panics_doc` | pedantic | Functions that can panic missing `# Panics` |
| `await_holding_lock` | correctness | `MutexGuard` held across `.await` — deadlock risk |
| `await_holding_refcell_ref` | correctness | `RefCell` borrow held across `.await` |
| `cloned_instead_of_copied` | pedantic | `.cloned()` on a `Copy` type — use `.copied()` |
| `needless_pass_by_value` | pedantic | Argument taken by value but only used by reference |
| `redundant_pattern_matching` | style | `if let Ok(_) = x` — use `x.is_ok()` |

### Pedantic Lints Worth Enabling

Enable these; suppress individually with `#[allow(...)]` where justified:

```rust
#![warn(
    clippy::pedantic,
    // These pedantic lints are high-signal; keep them warn, not allow:
    // missing_errors_doc, missing_panics_doc, must_use_candidate,
    // needless_pass_by_value, cast_possible_truncation, cast_lossless,
    // cloned_instead_of_copied
)]

// Suppress with justification at the site
#[allow(clippy::must_use_candidate)] // this fn is called for side effects only
pub fn register_provider(&mut self, name: &str, provider: Box<dyn Provider>) {
```

---

## Testing Conventions

Source: Rust Book Chapter 11, Cargo Book §Tests

### Three Test Types

| Type | Location | What it tests |
|---|---|---|
| Unit tests | `src/` file, `#[cfg(test)]` module | Private functions and internal logic |
| Integration tests | `tests/*.rs` | Public API as an external caller would use it |
| Doc tests | `///` examples with ```` ``` ```` | That examples in documentation compile and pass |

### Unit Test Conventions

```rust
// At the bottom of the file being tested
#[cfg(test)]
mod tests {
    use super::*;  // bring the module's private items into scope

    #[test]
    fn voice_id_rejects_empty_string() {
        let result = VoiceId::try_from("".to_owned());
        assert!(result.is_err());
    }

    #[test]
    fn voice_id_round_trips_through_display() {
        let id = VoiceId::try_from("nova".to_owned()).unwrap();
        assert_eq!(id.to_string(), "nova");
    }
}
```

Test function names are descriptive sentences in `snake_case`. Name them as
`thing_being_tested_condition_expected_result`.

### Integration Test Conventions

```
tests/
  voices.rs         ← tests for voice-related API
  synthesis.rs      ← tests for synthesis API
  common/
    mod.rs          ← shared test helpers (use mod.rs, not common.rs, to avoid
```                     Cargo treating it as a test file)

```rust
// tests/voices.rs
use fakoli_tts::{Client, VoiceId};

mod common;  // shared helpers from tests/common/mod.rs

#[tokio::test]
async fn list_voices_returns_non_empty_slice() -> anyhow::Result<()> {
    let client = common::test_client();
    let voices = client.list_voices().await?;
    assert!(!voices.is_empty());
    Ok(())
}
```

### `#[should_panic]` vs Returning `Result`

Prefer returning `Result<(), E>` from tests over `#[should_panic]`. The
`Result` form works with `?`, gives a clear error message on failure, and
composes with async test runners.

```rust
// Approved — error propagated with context
#[test]
fn parse_config_rejects_missing_key() -> Result<(), ConfigError> {
    let config = Config::from_str("")?;
    // unreachable — the ? above returns Err
    Ok(())
}

// Acceptable only when testing that a panic occurs
#[test]
#[should_panic(expected = "index out of bounds")]
fn sample_at_panics_on_out_of_bounds() {
    let chunk = AudioChunk::empty();
    chunk.sample_at(0);
}
```

---

## Workspace and Cargo Conventions

### Workspace Dependency Pattern

Source: Cargo Book §Workspaces, RFC 2906

Define all shared dependencies once in the root `Cargo.toml`. Members inherit
with `{ workspace = true }`. Features declared at both levels are additive.

```toml
# Cargo.toml (workspace root)
[workspace]
members = ["crates/core", "crates/cli", "crates/provider-elevenlabs"]
resolver = "2"

[workspace.dependencies]
# Pin versions once; all members agree on the same version
tokio       = { version = "1", features = ["rt-multi-thread", "macros"] }
serde       = { version = "1", features = ["derive"] }
thiserror   = "2"
anyhow      = "1"
tracing     = "0.1"
# Local crates
fakoli-core = { path = "crates/core" }
```

```toml
# crates/cli/Cargo.toml
[dependencies]
tokio    = { workspace = true }
anyhow   = { workspace = true }
tracing  = { workspace = true, features = ["log"] }  # additive: workspace + member features

fakoli-core = { workspace = true }

[dev-dependencies]
tokio = { workspace = true, features = ["test-util"] }
```

### Feature Flag Conventions

Feature flags must be **additive** — enabling a feature must not break code
that did not ask for it. Use the `"serde"` feature name (not `"with-serde"` or
`"use-serde"`) for optional serde support. Source: API Guidelines §C-FEATURE.

```toml
[features]
default = []
serde   = ["dep:serde"]      # gates serde derives on public types
tokio   = ["dep:tokio"]      # gates async API surface
```

---

## Backward-Compatible API Evolution

Source: RFC 1105 (API Evolution), Cargo Book §SemVer

### What Requires a Major Version Bump

| Change | Major? | Reason |
|---|---|---|
| Rename or remove a public item | Yes | Breaks all callers |
| Add a variant to a public enum | Yes | Breaks exhaustive `match` arms |
| Add a non-defaulted method to a public trait | Yes | Breaks all implementations |
| Tighten type bounds | Yes | Existing uses become invalid |
| Change function signature | Yes | Every call site breaks |
| Add public fields to a struct | Yes | Breaks struct literal construction |

### What Is Safe in a Minor Version

| Change | Minor? | Notes |
|---|---|---|
| Add a new public function or method | Yes | Callers do not need to update |
| Add a defaulted trait method | Yes | Existing `impl` blocks still valid |
| Implement a non-fundamental trait | Yes | e.g., adding `Display` |
| Add a new public type | Yes | |
| Loosen type bounds | Yes | Existing callers still valid |

### Deprecation Workflow

```rust
// Step 1 — add #[deprecated] with a note pointing to the replacement
#[deprecated(since = "2.1.0", note = "use `Client::synthesize_with` instead")]
pub fn synthesize(&self, text: &str) -> Result<Vec<u8>, Error> {
    self.synthesize_with(text, SynthesisOptions::default())
}

// Step 2 — keep the pub use alias during the grace period
// In lib.rs, if the item has moved modules:
#[allow(deprecated)]
pub use old_module::OldName;
```

Remove deprecated items only at the next major version. Mark the removal in
`CHANGELOG.md` with the version it was deprecated in.

### Sealed Traits

Source: API Guidelines §C-SEALED

When a trait is only meant to be implemented inside your crate (preventing
downstream impls from breaking you when you add methods), use the sealed trait
pattern:

```rust
// In a private module — the supertrait is not accessible outside this crate
mod private {
    pub trait Sealed {}
}

// The public trait requires the private supertrait
pub trait Provider: private::Sealed {
    fn synthesize(&self, text: &str) -> Vec<u8>;
    // Safe to add new methods here without a semver break,
    // because no external code can impl Provider
}

// Only types we impl Sealed for can impl Provider
impl private::Sealed for ElevenLabsProvider {}
impl Provider for ElevenLabsProvider { ... }
```

### `#[non_exhaustive]` on Enums and Structs

Mark enums and structs `#[non_exhaustive]` when you want to add variants or
fields in future minor versions without a semver break. Downstream code cannot
use exhaustive `match` or struct literal construction on `#[non_exhaustive]`
types from external crates.

```rust
#[non_exhaustive]
pub enum AudioFormat {
    Mp3,
    Opus,
    Aac,
    // Adding Flac later will be a minor version, not a major
}
```

---

## Async Conventions

Source: tokio documentation, Rust async book

### `Send` Bounds in Async APIs

For library functions and trait methods that will be used with `tokio::spawn`,
the returned futures must be `Send`. Ensure types held across `.await` are
`Send`.

```rust
// Approved — future is Send because all held types are Send
pub async fn fetch_voices(client: &Client) -> Result<Vec<Voice>, Error> {
    let response = client.http.get("/voices").send().await?;
    Ok(response.json().await?)
}

// Common bug — Rc<T> is not Send; this future cannot be spawned
async fn bad_example() {
    let counter = std::rc::Rc::new(0);
    some_async_op().await;
    println!("{counter}");  // Rc held across await — future is !Send
}
```

### Async Trait Methods

The `async_trait` crate and the newer `trait_variant` crate (stable from Rust
1.75 for `async fn in trait`) both work. Prefer native `async fn` in traits
(Rust 1.75+) for new code. Use `trait_variant::make` to generate a `Send`
version of an async trait:

```rust
#[trait_variant::make(SynthesizerSend: Send)]
pub trait Synthesizer {
    async fn synthesize(&self, text: &str) -> Result<Vec<u8>, Error>;
}

// Use SynthesizerSend as the bound when spawning tasks
pub fn spawn_synthesis(synthesizer: impl SynthesizerSend + 'static, text: String) {
    tokio::spawn(async move {
        let _ = synthesizer.synthesize(&text).await;
    });
}
```

### Blocking Code in Async Context

Never call blocking operations (filesystem I/O, CPU-heavy work, blocking
`std::sync::Mutex::lock()` with long contention) directly in async functions.
Use `tokio::task::spawn_blocking` for CPU-bound or blocking-I/O work.

```rust
// Rejected — blocks the async executor thread
async fn hash_file(path: &Path) -> Result<[u8; 32], io::Error> {
    let data = std::fs::read(path)?;  // blocking read in async context
    Ok(sha256(&data))
}

// Approved — offloaded to the blocking thread pool
async fn hash_file(path: PathBuf) -> Result<[u8; 32], io::Error> {
    tokio::task::spawn_blocking(move || {
        let data = std::fs::read(&path)?;
        Ok(sha256(&data))
    })
    .await
    .unwrap() // the JoinError only occurs if spawn_blocking panics
}
```

---

## What a Senior Reviewer Always Checks

### MUST Fix (block merge)

1. **`unwrap()` or `expect()` without justification** in library code.
   Use `?` for propagation. Use `.expect("invariant: X because Y")` with a
   sentence-length message when the invariant truly cannot be violated.

2. **`panic!` in a library crate** without documentation in `# Panics`.
   If the panic is not documenting a programmer contract, convert it to
   `Result`.

3. **`anyhow` in a library's public API.** Callers lose the ability to
   handle specific errors. Use `thiserror`.

4. **Missing `Send + Sync` on error types.** Without them, the error cannot
   be used with `anyhow`, passed across thread boundaries, or returned from
   `tokio::spawn`.

5. **`impl Into<T>` parameter instead of `impl From<T>`-based pattern.**
   Accept `impl Into<T>` in function signatures (this is fine), but implement
   `From<T>`, never `Into<U>` directly.

6. **Holding a `Mutex` lock or `RefCell` borrow across `.await`.**
   This deadlocks on single-threaded executors and panics on `RefCell`.

7. **Breaking semver:** adding an enum variant, removing a public item, or
   adding a non-defaulted trait method without a major version bump.

8. **Missing `# Errors`, `# Panics`, or `# Safety` doc sections** on
   public functions that return `Result`, can panic, or are `unsafe`.

### SHOULD Fix (fix unless justified)

9. **`as` casts for numeric conversion.** Use `From::from(x)` for lossless
   conversions. Use `T::try_from(x)?` for fallible narrowing conversions.
   `x as T` silently truncates and is rejected by `clippy::cast_possible_truncation`.

10. **Cloning to satisfy the borrow checker.** Redesign the ownership, or
    document why the clone is intentional.

11. **`pub use *` (glob re-exports).** Makes the public API surface invisible.
    Name every export.

12. **Raw indexing `vec[i]`** without a prior bounds check. Use `.get(i)` and
    handle `None`, or ensure the bounds are structurally guaranteed and
    document why.

13. **Conversion methods named `get_foo()`.** RFC 430 / API Guidelines drop the
    `get_` prefix. `foo()` is the correct name.

14. **`impl Into<Foo>` implemented directly.** Implement `From<T>` instead.

### CONSIDER (author's discretion)

15. **Newtype wrapper for primitive arguments.** When a function takes two or
    more arguments of the same primitive type, a newtype prevents silent
    argument transposition.

16. **Builder for structs with four or more optional fields.**

17. **`#[non_exhaustive]` on public enums** that may grow new variants in
    future minor versions.

18. **Sealed trait** if the trait is an implementation detail, not a
    user-extension point.

### Idiomatic vs Non-Idiomatic Cheatsheet

| Non-Idiomatic | Idiomatic | Authority |
|---|---|---|
| `impl Into<Foo> for Bar` | `impl From<Bar> for Foo` | API Guidelines §C-CONV-TRAITS |
| `fn get_name(&self)` | `fn name(&self)` | API Guidelines §C-GETTER |
| `x.clone()` on an `Arc` | `Arc::clone(&x)` | community consensus |
| `UUID`, `HTTPClient` | `Uuid`, `HttpClient` | RFC 430 §C-CASE |
| `x as u8` (truncating) | `u8::try_from(x)?` | clippy::cast_possible_truncation |
| `.unwrap()` | `.expect("invariant: ...")` or `?` | clippy::unwrap_used |
| `vec[i]` | `vec.get(i).ok_or(...)` | clippy::indexing_slicing |
| `anyhow` in lib public API | `thiserror` named enum | community consensus |
| `bool` arg: `f(true, false)` | `f(Mode::Fast, Output::File)` | API Guidelines §C-CUSTOM-TYPE |
| `pub struct Foo { pub field: T }` | `pub struct Foo { field: T }` + getter | API Guidelines §C-STRUCT-PRIVATE |
| Adding enum variant in minor | `#[non_exhaustive]` or major bump | RFC 1105 |
| `pub use module::*` | Named re-exports in `lib.rs` | community consensus |
| `for i in 0..vec.len()` | `for item in &vec` | clippy::style |
| Inline `mod foo { ... }` | `mod.rs` / separate file | community consensus |
| `#[derive]` on generic structs with bounds | Bounds only in `impl`, not `struct` | API Guidelines §C-STRUCT-BOUNDS |
