# TypeScript Design Guide

A reference for the guido agent's TypeScript design philosophy, translated from
decades of Python design decisions into the idioms that make TypeScript code
correct, readable, and maintainable.

## Naming and Formatting

Consistency matters more than any individual rule. The conventions below are
widely adopted across the TypeScript ecosystem and enforced by tools like ESLint
and Prettier.

### Naming Conventions

| Symbol | Convention | Example |
|---|---|---|
| Files | `kebab-case` | `audio-processor.ts` |
| Variables | `camelCase` | `voiceId`, `maxRetryCount` |
| Functions / Methods | `camelCase` | `processAudio()`, `listVoices()` |
| Classes | `PascalCase` | `AudioProcessor`, `TTSProvider` |
| Interfaces | `PascalCase` (no `I` prefix) | `ProviderConfig`, `SpeakResult` |
| Type aliases | `PascalCase` | `VoiceId`, `AudioFormat` |
| Enums | `PascalCase` (members `PascalCase`) | `AudioFormat.Mp3` — but prefer union types |
| Constants | `UPPER_CASE` | `MAX_RETRY_COUNT`, `DEFAULT_RATE` |
| Private class members | `camelCase` (use `#` for true private) | `#cache`, `#registry` |
| Type parameters | Single cap or descriptive `PascalCase` | `T`, `TResult`, `TValue` |

The `I` prefix on interfaces (`IUser`, `IProvider`) is a C# convention. Drop it.
The type system makes the interface / class distinction clear without the prefix.

### Line Length and Formatting

Prettier defaults to 80 characters with an acceptable print width of 100. The
principle is unchanged from PEP 8: a line should fit on a screen without
scrolling. When a line wraps, wrap at a logical boundary.

```typescript
// Approved — logical boundary, trailing comma signals the list continues
const result = await synthesize({
  text,
  voiceId,
  outputFormat: "mp3",
  speed: 1.0,
});

// Rejected — all arguments on one line, hard to scan and add to
const result = await synthesize({ text, voiceId, outputFormat: "mp3", speed: 1.0 });
```

Trailing commas in multi-line argument lists and object literals are required.
They produce cleaner diffs: adding a new item changes one line, not two.

```typescript
// Approved — destructuring with defaults, trailing comma
function buildHeaders({
  apiKey,
  contentType = "application/json",
  timeout = 30_000,
}: RequestOptions): Record<string, string> {
  return {
    Authorization: `Bearer ${apiKey}`,
    "Content-Type": contentType,
  };
}

// Rejected — positional parameters obscure intent
function buildHeaders(apiKey: string, contentType: string, timeout: number) { ... }
```

## Design Principles

The Zen of Python translates directly. The language changes; the philosophy does
not.

### "Explicit is better than implicit."

TypeScript's `strict: true` is the mechanical enforcement of this principle.
Enable it unconditionally. Never use `any` in a public API. Always annotate
return types on exported functions — do not rely on inference to document intent.

```typescript
// Approved — explicit return type, named parameters, strict types
async function getUser(
  userId: string,
  options: { includeDeleted?: boolean } = {},
): Promise<User | null> {
  ...
}

// Rejected — implicit return type, positional boolean, any leaks behavior
async function getUser(userId: any, includeDeleted?: boolean) {
  ...
}
```

`tsconfig.json` minimum:

```json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true
  }
}
```

### "Simple is better than complex."

Prefer the chain that reads as a sentence over the one that requires a diagram.
`filter` then `map` is understood immediately. A `reduce` that rebuilds an array
is not.

```typescript
// Approved — reads left to right, each step does one thing
const activeNames = users
  .filter((user) => user.isActive)
  .map((user) => user.name);

// Rejected — forces the reader to simulate the accumulator in their head
const activeNames = users.reduce<string[]>((acc, user) => {
  if (user.isActive) acc.push(user.name);
  return acc;
}, []);
```

### "Readability counts."

Name things for the reader, not the author. The author knows what `tp` means
today. Nobody knows next month.

```typescript
// Approved — self-documenting
const totalPrice = cart.items.reduce((sum, item) => sum + item.price, 0);

// Rejected — requires archaeology to understand
const tp = c.i.reduce((s, i) => s + i.p, 0);
```

### "Errors should never pass silently."

Catch specific error types. Use `instanceof` narrowing. An untyped `catch` block
that swallows its payload is not error handling — it is denial.

```typescript
// Approved — typed guard, context preserved, re-thrown
try {
  result = await api.fetch(url);
} catch (error: unknown) {
  if (error instanceof TimeoutError) {
    logger.warn("Fetch timed out", { url, error });
    throw error;
  }
  throw new FetchError(`Unexpected failure fetching ${url}`, { cause: error });
}

// Rejected — bare catch, silent swallow, no context
try {
  result = await api.fetch(url);
} catch {
  // nothing
}
```

### "If the implementation is hard to explain, it is a bad idea."

If you cannot describe what a function does in one sentence, split it. A function
that fetches, transforms, validates, and persists is four functions wearing a
coat.

## Interfaces and Structural Typing

TypeScript's type system is structurally typed by default. This is the language's
answer to Python's Protocols — and it requires no decorator, no import, and no
explicit declaration of intent.

### Interface vs Type

Use `interface` for object shapes that may be extended or implemented by a class.
Use `type` for unions, intersections, computed shapes, and aliases that are not
meant to be extended.

```typescript
// interface — extensible object shape, class can implement it
interface TTSProvider {
  synthesize(text: string, voiceId: string): Promise<Uint8Array>;
  listVoices(): Promise<string[]>;
  stream(text: string, voiceId: string): AsyncIterable<Uint8Array>;
}

// type — union of literals, not a shape to extend
type AudioFormat = "mp3" | "opus" | "aac" | "flac";

// type — intersection, computed from two shapes
type AuthenticatedRequest = Request & { userId: string };
```

### Implicit Satisfaction

A class satisfies an interface by implementing its members. No `implements`
clause is required for structural compatibility. Use `implements` when you want
the compiler to verify the contract at the class definition — which is usually
worth doing.

```typescript
// OpenAIProvider satisfies TTSProvider structurally.
// The implements clause makes the contract explicit and catches drift early.
class OpenAIProvider implements TTSProvider {
  async synthesize(text: string, voiceId: string): Promise<Uint8Array> {
    const response = await this.#client.audio.speech.create({
      input: text,
      voice: voiceId,
      model: "tts-1",
    });
    return new Uint8Array(await response.arrayBuffer());
  }

  async listVoices(): Promise<string[]> {
    return ["alloy", "echo", "fable", "onyx", "nova", "shimmer"];
  }

  async *stream(text: string, voiceId: string): AsyncIterable<Uint8Array> {
    const response = await this.#client.audio.speech.create({
      input: text,
      voice: voiceId,
      stream: true,
    });
    for await (const chunk of response.body) {
      yield chunk;
    }
  }
}
```

### Interface Segregation

Interfaces should be small — 1 to 5 members. A large interface is a sign the
abstraction is wrong. Split it.

```typescript
// Rejected — one interface forcing all implementors to handle streaming
interface TTSProvider {
  synthesize(...): Promise<Uint8Array>;
  listVoices(): Promise<string[]>;
  stream(...): AsyncIterable<Uint8Array>;
  getUsage(): Promise<UsageStats>;
  deleteVoice(voiceId: string): Promise<void>;
  cloneVoice(audioSample: Uint8Array): Promise<string>;
}

// Approved — focused interfaces, compose as needed
interface Synthesizer {
  synthesize(text: string, voiceId: string): Promise<Uint8Array>;
}

interface VoiceManager {
  listVoices(): Promise<string[]>;
  deleteVoice(voiceId: string): Promise<void>;
  cloneVoice(audioSample: Uint8Array): Promise<string>;
}

interface StreamingSynthesizer extends Synthesizer {
  stream(text: string, voiceId: string): AsyncIterable<Uint8Array>;
}
```

### Runtime Type Narrowing

TypeScript interfaces are erased at runtime. For runtime checks, use
discriminated unions or Zod schemas — not `instanceof` against an interface.

```typescript
// Discriminated union — the kind field survives at runtime
type ProviderEvent =
  | { kind: "synthesis-complete"; durationMs: number; bytes: number }
  | { kind: "rate-limited"; retryAfterMs: number }
  | { kind: "error"; message: string; code: string };

function handleEvent(event: ProviderEvent): void {
  switch (event.kind) {
    case "synthesis-complete":
      logger.info("Done", { duration: event.durationMs });
      break;
    case "rate-limited":
      scheduleRetry(event.retryAfterMs);
      break;
    case "error":
      throw new ProviderError(event.message, event.code);
    default: {
      // Exhaustive check — TypeScript errors here if a case is missing
      const _exhaustive: never = event;
      throw new Error(`Unhandled event: ${JSON.stringify(_exhaustive)}`);
    }
  }
}
```

## Data Modeling

TypeScript has no built-in equivalent of Python's `@dataclass(frozen=True)`, but
the same goals — immutability, structural equality, self-documentation — are
achievable with `readonly`, `Readonly<T>`, `as const`, and Zod.

### readonly Properties

Mark every property of a value object `readonly`. Mutation of data that flows
through a pipeline is a source of bugs that are hard to trace.

```typescript
// Approved — all properties readonly, no method behavior needed
interface VoiceConfig {
  readonly voiceId: string;
  readonly model: string;
  readonly speed: number;
  readonly outputFormat: AudioFormat;
}

// Construction — explicit, validated at the call site
const config: VoiceConfig = {
  voiceId: "nova",
  model: "tts-1",
  speed: 1.0,
  outputFormat: "mp3",
};
```

### Readonly<T> for Deep Immutability

`Readonly<T>` makes a type's top-level properties non-writable. For deeply nested
structures, use `as const` at the value level or a recursive `DeepReadonly<T>`
helper.

```typescript
type DeepReadonly<T> = {
  readonly [K in keyof T]: T[K] extends object ? DeepReadonly<T[K]> : T[K];
};

// as const — infers a deeply readonly literal type
const DEFAULT_CONFIG = {
  model: "tts-1",
  speed: 1.0,
  outputFormat: "mp3",
} as const;
// typeof DEFAULT_CONFIG is { readonly model: "tts-1"; readonly speed: 1.0; readonly outputFormat: "mp3" }
```

### Class with readonly When Behavior Is Needed

If the object needs methods — validation, transformation, derived properties —
use a class with `readonly` properties and a private constructor that enforces
invariants.

```typescript
class AudioChunk {
  readonly data: Uint8Array;
  readonly sampleRate: number;
  readonly channels: number;

  private constructor(data: Uint8Array, sampleRate: number, channels: number) {
    this.data = data;
    this.sampleRate = sampleRate;
    this.channels = channels;
  }

  static create(
    data: Uint8Array,
    sampleRate: number,
    channels: number = 1,
  ): AudioChunk {
    const VALID_RATES = new Set([8000, 16000, 22050, 44100, 48000]);
    if (!VALID_RATES.has(sampleRate)) {
      throw new RangeError(`Unsupported sample rate: ${sampleRate}`);
    }
    if (data.byteLength === 0) {
      throw new RangeError("Audio chunk cannot be empty");
    }
    return new AudioChunk(data, sampleRate, channels);
  }

  get durationMs(): number {
    return (this.data.byteLength / (this.sampleRate * this.channels * 2)) * 1000;
  }
}
```

### Zod for Runtime Validation

When data crosses a boundary — API response, user input, config file — validate
it with Zod. Zod schemas produce an inferred TypeScript type and a runtime
validator in one declaration.

```typescript
import { z } from "zod";

const VoiceConfigSchema = z.object({
  voiceId: z.string().min(1),
  model: z.enum(["tts-1", "tts-1-hd"]).default("tts-1"),
  speed: z.number().min(0.25).max(4.0).default(1.0),
  outputFormat: z.enum(["mp3", "opus", "aac", "flac"]).default("mp3"),
});

type VoiceConfig = z.infer<typeof VoiceConfigSchema>;

// At the boundary — parse throws ZodError with field-level detail on failure
const config = VoiceConfigSchema.parse(rawInput);
```

### Reject Mutable Defaults in Parameter Positions

Mutable object or array literals as default parameter values are shared across
calls in JavaScript. Use factory functions or `as const` tuples instead.

```typescript
// Rejected — the metadata object is shared across all calls
function createProvider(options = { retries: 3, tags: [] }) { ... }

// Approved — each call gets a fresh object from the type signature
function createProvider(options?: { retries?: number; tags?: string[] }) {
  const { retries = 3, tags = [] } = options ?? {};
  ...
}
```

## Code Review Patterns

Reviews are methodical. Read line by line, consider alternatives, and assign
severity levels. Every comment should state what to do, not just what is wrong.

### Severity Levels

| Level | Meaning | Action Required |
|---|---|---|
| **MUST** | Correctness or security issue | Block merge until fixed |
| **SHOULD** | Clear improvement, good reasons to do it | Fix before merge unless justified |
| **CONSIDER** | Stylistic preference, idiomatic alternative | Author's discretion |
| **NIT** | Minor style issue | Optional; fix if trivial |

### Review Comment Style

```
MUST: This will throw at runtime if `response.data` is undefined.
Add a null check or use optional chaining before line 47.

SHOULD: The nested ternary on line 23 is hard to parse.
Extract into an if/else block or a named helper function.

CONSIDER: This could be a discriminated union instead of a plain string status.
The union narrows the type in each branch automatically.

NIT: Variable name `d` should be `durationMs` for readability.
```

### What This Guide Always Checks

1. **Type annotations.** No `any` in any public API. Private helpers should be
   annotated where the inferred type is not obvious. A return type of `any` in an
   exported function is a MUST-fix.

2. **Error specificity.** No bare `catch {}`. No `catch (e)` where `e` is used
   as `any`. Every catch block must narrow the error type with `instanceof` or
   check `error instanceof Error` before accessing `.message`.

3. **Immutability of defaults.** No mutable object or array literals in default
   parameter positions. No `const config = {}` that grows properties over time
   via assignment.

4. **Import organization.** Framework and runtime imports first, then
   third-party packages, then local modules. One blank line between groups. No
   mixing of groups.

   ```typescript
   // Framework / runtime
   import { createServer } from "node:http";

   // Third-party
   import { z } from "zod";
   import OpenAI from "openai";

   // Local
   import { ProviderRegistry } from "./registry.js";
   import type { VoiceConfig } from "./types.js";
   ```

5. **Barrel file exports.** Public API modules should have an `index.ts` that
   re-exports only the public surface. Do not use `export *` — it makes the
   public API invisible and causes accidental exposure of internal types.

   ```typescript
   // src/index.ts — explicit, auditable public API
   export { synthesize, listVoices } from "./core.js";
   export type { VoiceConfig, SpeakResult } from "./types.js";
   export { FakoliError, ProviderNotFoundError } from "./errors.js";
   ```

6. **Strict mode.** `strict: true` must be present in `tsconfig.json`. If a PR
   introduces a `// @ts-ignore` without an explanatory comment on the same line,
   that is a MUST-fix.

### Idiomatic vs Non-Idiomatic TypeScript

| Non-Idiomatic | Idiomatic |
|---|---|
| `x as any` | Type narrowing with a user-defined type guard |
| `for (let i = 0; i < items.length; i++)` | `for (const item of items)` |
| `enum Direction { Up = "UP", Down = "DOWN" }` (when union suffices) | `type Direction = "up" \| "down"` |
| `interface IUser` | `interface User` (no `I` prefix) |
| `x !== undefined && x !== null` | `x != null` or `x?.property ?? fallback` |
| `promise.then(a).then(b).catch(c)` | `async/await` with `try/catch` |
| Nested ternary `a ? b : c ? d : e` | `if/else` block or extracted function |
| `Object.keys(obj).forEach(...)` | `for (const [key, value] of Object.entries(obj))` |
| `Function` type | Specific signature: `(input: string) => Promise<void>` |
| `!value` to check for null/undefined | `value == null` — explicit and correct for both |

## What This Guide Approves

- **`strict: true`** — the foundational compiler setting. Non-negotiable.
- **Discriminated unions** — model state machines and variant types; narrows
  automatically in switch statements.
- **`satisfies` operator** — validate that a literal conforms to a type without
  widening the inferred type.
  ```typescript
  const config = {
    model: "tts-1",
    outputFormat: "mp3",
  } satisfies Partial<VoiceConfig>;
  // config.model is still the literal "tts-1", not string
  ```
- **`as const`** — freeze object literals and array literals into their narrowest
  literal types.
- **Branded types** — distinguish values that share a primitive representation
  but mean different things.
  ```typescript
  type VoiceId = string & { readonly _brand: "VoiceId" };
  type UserId = string & { readonly _brand: "UserId" };

  function toVoiceId(raw: string): VoiceId {
    if (raw.trim().length === 0) throw new RangeError("voiceId cannot be empty");
    return raw as VoiceId;
  }
  ```
- **`using` and `Symbol.dispose`** — deterministic resource cleanup without
  try/finally boilerplate (TypeScript 5.2+).
  ```typescript
  async function withTempFile(work: (path: string) => Promise<void>): Promise<void> {
    await using file = await createTempFile();
    await work(file.path);
    // file[Symbol.asyncDispose]() called automatically on scope exit
  }
  ```
- **Exhaustive switch with `never`** — compiler-verified exhaustion of
  discriminated unions. When a new variant is added, every switch that lacks a
  case becomes a type error.
- **Small interfaces** — 1 to 5 members. Compose larger contracts via
  intersection types.
- **`readonly` by default** — prefer `readonly` on every property until mutation
  is proven necessary, not the other way around.

## What This Guide Rejects

- **`any`** — it silences the type checker entirely. Use `unknown` and narrow.
  Every `any` in a public API is a correctness hole.
- **`@ts-ignore` without a comment** — suppressing an error without explaining
  why makes future refactors dangerous. The required form:
  ```typescript
  // @ts-ignore: upstream type definition missing overload for callback form
  legacyLibrary.onEvent("data", handler);
  ```
- **Deep class hierarchies** — more than one level of inheritance is a signal
  that composition or interfaces would serve better.
- **`namespace`** — a TypeScript-specific feature that predates ES modules. Use
  ES module exports instead.
- **`enum` when a union type suffices** — enums are compiled to runtime objects
  and produce surprising behavior with string comparisons. A union of string
  literals is zero-overhead, fully type-safe, and JSON-transparent.
  ```typescript
  // Rejected
  enum AudioFormat { Mp3 = "mp3", Opus = "opus", Aac = "aac" }

  // Approved
  type AudioFormat = "mp3" | "opus" | "aac";
  const AUDIO_FORMATS = ["mp3", "opus", "aac"] as const;
  ```
- **`export *`** — makes the module's public surface invisible and risks
  exporting internal types by accident. Name every export.
- **Non-null assertion `!` when a null check is possible** — `user!.name` hides
  the invariant. `if (user == null) throw ...` makes it a verified invariant.
- **`as` casting when a type guard is possible** — casting tells the compiler
  to trust you. A guard proves the type at runtime.
  ```typescript
  // Rejected — the cast is a promise the compiler cannot verify
  const provider = registry.get(name) as OpenAIProvider;

  // Approved — the guard proves the shape before use
  const provider = registry.get(name);
  if (!(provider instanceof OpenAIProvider)) {
    throw new ProviderNotFoundError(`Expected OpenAIProvider, got: ${name}`);
  }
  ```
- **`Function` type** — write the signature. `Function` accepts anything and
  returns `any`. It is `any` wearing a coat.
- **`Object` and `{}` types** — `{}` matches every non-null value in TypeScript.
  It is not a useful constraint. Use `Record<string, unknown>` or a named
  interface.
- **Catching and re-throwing without `cause`** — loses the original stack and
  context. Always chain errors.

  ```typescript
  // Rejected — the original NetworkError and its stack are gone
  try {
    result = await fetch(url);
  } catch {
    throw new Error("Could not load data");
  }

  // Approved — the original error is preserved as cause, full chain intact
  try {
    result = await fetch(url);
  } catch (error: unknown) {
    throw new FetchError(`Could not load data from ${url}`, { cause: error });
  }
  ```
