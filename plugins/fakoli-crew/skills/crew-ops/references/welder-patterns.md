# Welder Patterns: Integration & Backward Compatibility Field Manual

Researched: 2026-04-02
Sources: Cargo Book, Node.js Docs, PEP 387, PEP 562, semver-ts.org, Rust By Example, Vitest Docs, pnpm Docs

This is the welder's field manual. Every pattern shows TypeScript, Python, and Rust side by side.
The welder's prime directive: **never break existing callers**.

---

## 0. Project Detection

Before doing anything, identify the language by the manifest file present:

| File present | Language | Package manager |
|---|---|---|
| `Cargo.toml` | Rust | cargo |
| `pyproject.toml` | Python | uv / pip / hatch |
| `setup.py` (legacy) | Python | pip |
| `package.json` | TypeScript / JS | pnpm / bun / npm |
| `pnpm-workspace.yaml` | TypeScript monorepo | pnpm |
| Multiple of the above | Polyglot monorepo | check subdirectories |

A `Cargo.lock` at root signals a Rust application (not a library). A `pnpm-workspace.yaml` alongside `package.json` means a multi-package TypeScript workspace.

---

## 1. Re-Export for Backward Compatibility

The single most important integration pattern. When code moves, old import paths must keep working.

### TypeScript — Barrel Re-Export

The barrel file (`index.ts`) re-exports from wherever the implementation actually lives.

```typescript
// src/index.ts — the public API surface

// Direct re-export (name unchanged, path changed)
export { UserService } from './services/user-service';

// Aliased re-export (old name → new name at new path)
export { NewEmailService as EmailService } from './services/email';

// Re-export entire namespace
export * from './models';

// Re-export type separately (tree-shakeable)
export type { UserRecord, UserOptions } from './types/user';
```

When internal files move, update only the barrel — consumer imports stay identical.

**Wildcard vs named**: prefer explicit `export { X }` over `export *`. Wildcard exports prevent bundlers from eliminating unused code and can create name collisions.

### Python — `__init__.py` Re-Export

```python
# mypackage/__init__.py

# New module is services/user.py — old callers import from mypackage directly
from .services.user import UserService

# Aliased re-export: new class name, old public name
from .services.email import NewEmailService as EmailService

# Explicit public API surface
__all__ = [
    "UserService",
    "EmailService",
]
```

Old callers doing `from mypackage import UserService` continue to work unchanged.

**`__all__`**: controls what `from mypackage import *` includes, and signals intent to static analyzers. Always define it when you care about the public API surface.

### Rust — `pub use` Re-Export

```rust
// src/lib.rs

// Re-export from new location under the old path
pub use crate::services::user::UserService;

// Re-export with alias (old name kept public, new name is the real one)
pub use crate::services::email::NewEmailService as EmailService;

// Re-export an entire module
pub use crate::models;
```

Old callers doing `use mylib::UserService` continue to work. The `pub use` declaration creates a stable public path regardless of where the item lives internally.

**Crate boundary note**: `pub use` in `lib.rs` makes items appear to live there in documentation (rustdoc inlines them). This is intended — it hides internal module structure from callers.

---

## 2. Deprecation — Warn Before Removing

Never remove. Warn first, remove later (at least one major version later).

### TypeScript — JSDoc `@deprecated`

```typescript
// src/index.ts

/**
 * @deprecated since 1.4.0 — use `NewEmailService` instead.
 * Will be removed in 2.0.0.
 */
export { NewEmailService as EmailService } from './services/email';

// For deprecated functions:
/**
 * @deprecated since 1.3.0 — use `sendTransactional(opts)` instead.
 */
export function sendEmail(to: string, subject: string, body: string): void {
  console.warn(
    '[DEPRECATED] sendEmail() is deprecated. Use sendTransactional() instead.'
  );
  sendTransactional({ to, subject, body });
}
```

TypeScript itself does not emit runtime warnings for `@deprecated` — the annotation is for IDEs and static analysis. If you need a runtime warning, add it manually as shown above.

TypeScript 5.5+ strikethrough display in IDEs: any call site referencing a `@deprecated` symbol shows strikethrough text in VS Code.

### Python — `warnings.warn` + `@deprecated`

**For functions and methods:**

```python
import warnings

def send_email(to: str, subject: str, body: str) -> None:
    warnings.warn(
        "send_email() is deprecated since 1.3.0. "
        "Use send_transactional(opts) instead. "
        "Will be removed in 2.0.0.",
        DeprecationWarning,
        stacklevel=2,   # points warning to the caller, not this function
    )
    send_transactional({"to": to, "subject": subject, "body": body})
```

**`stacklevel=2` is mandatory.** Without it, the warning points to the inside of `send_email`, which is useless. `stacklevel=2` makes it point to the code that called `send_email`.

**Python 3.13+: `@warnings.deprecated` decorator (PEP 702):**

```python
from warnings import deprecated

@deprecated("Use send_transactional() instead. Removed in 2.0.")
def send_email(to: str, subject: str, body: str) -> None:
    send_transactional({"to": to, "subject": subject, "body": body})
```

**For deprecated module-level attributes (PEP 562, Python 3.7+):**

```python
# mypackage/__init__.py
import warnings

# New name lives here
from .services.email import NewEmailService

_deprecated_names = {
    "OldEmailService": "NewEmailService",
}

def __getattr__(name: str):
    if name in _deprecated_names:
        new_name = _deprecated_names[name]
        warnings.warn(
            f"{name} is deprecated. Use {new_name} instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return globals()[new_name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

Old code doing `from mypackage import OldEmailService` now emits a `DeprecationWarning` at the import site and still works.

**Testing deprecation warnings with pytest:**

```python
import pytest

def test_old_name_warns():
    with pytest.warns(DeprecationWarning, match="OldEmailService is deprecated"):
        from mypackage import OldEmailService

def test_warning_in_function():
    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        send_email("a@b.com", "hi", "body")
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "send_email" in str(w[0].message)
```

### Rust — `#[deprecated]` Attribute

```rust
// src/lib.rs

#[deprecated(since = "1.3.0", note = "use send_transactional() instead")]
pub fn send_email(to: &str, subject: &str, body: &str) {
    send_transactional(&SendOpts { to, subject, body });
}

// Deprecated re-export (old path → new item):
#[deprecated(since = "1.4.0", note = "use EmailService instead")]
pub use crate::services::email::NewEmailService as OldEmailService;
```

Rust emits a compiler warning at every call site that uses a deprecated item. No runtime cost.

**Known limitation**: `#[deprecated]` on a `pub use` re-export does not always emit a warning as expected (Rust issue #85388). Prefer deprecating the item at its definition site when possible.

**Lint control at call sites:**

```rust
// Suppress the warning for one specific call (migration code):
#[allow(deprecated)]
fn migrate_legacy_email(to: &str) {
    send_email(to, "subject", "body");
}
```

---

## 3. The Adapter Pattern

An adapter translates the interface a caller knows (the old contract) into the interface a new implementation provides (the new contract). The caller never changes.

### TypeScript — Class Adapter

```typescript
// The new implementation with a different interface
class NewEmailService {
  sendTransactional(opts: { to: string; subject: string; body: string }): void {
    // ...
  }
}

// The old interface callers depend on
interface LegacyEmailClient {
  send(to: string, subject: string, body: string): void;
}

// Adapter: wraps new, exposes old
class LegacyEmailAdapter implements LegacyEmailClient {
  constructor(private service: NewEmailService) {}

  send(to: string, subject: string, body: string): void {
    this.service.sendTransactional({ to, subject, body });
  }
}

// Wire it:
const adapter = new LegacyEmailAdapter(new NewEmailService());
// Existing code that expects LegacyEmailClient works unchanged:
legacySystemThatCallsSend(adapter);
```

### Python — Adapter Class

```python
from dataclasses import dataclass

class NewEmailService:
    def send_transactional(self, opts: dict) -> None:
        ...

class LegacyEmailAdapter:
    """Wraps NewEmailService, exposes the old send(to, subject, body) API."""

    def __init__(self, service: NewEmailService) -> None:
        self._service = service

    def send(self, to: str, subject: str, body: str) -> None:
        self._service.send_transactional({"to": to, "subject": subject, "body": body})

# Wire it:
adapter = LegacyEmailAdapter(NewEmailService())
# Any code expecting an object with .send() still works:
legacy_system_that_calls_send(adapter)
```

### Rust — Adapter with Trait

```rust
// Old trait that callers depend on
pub trait LegacyEmailClient {
    fn send(&self, to: &str, subject: &str, body: &str);
}

// New implementation with a different interface
pub struct NewEmailService;

impl NewEmailService {
    pub fn send_transactional(&self, opts: SendOpts) { /* ... */ }
}

// Adapter struct wrapping the new service
pub struct LegacyEmailAdapter {
    service: NewEmailService,
}

impl LegacyEmailAdapter {
    pub fn new(service: NewEmailService) -> Self {
        Self { service }
    }
}

// Implement the old trait on the adapter
impl LegacyEmailClient for LegacyEmailAdapter {
    fn send(&self, to: &str, subject: &str, body: &str) {
        self.service.send_transactional(SendOpts { to, subject, body });
    }
}

// Wire it:
let adapter = LegacyEmailAdapter::new(NewEmailService);
legacy_system_that_needs_legacy_email_client(adapter);
```

---

## 4. The Facade Pattern

A facade provides a simplified, stable interface over a complex or evolving subsystem. All callers go through the facade, so the internals can be refactored freely.

### TypeScript — Facade Function/Class

```typescript
// facade.ts — the stable surface
// Internals can change; only this file's signature is a promise to callers.

import { UserRepository } from './db/user-repository';
import { EmailService } from './services/email';
import { AuditLogger } from './logging/audit';

export async function registerUser(
  email: string,
  password: string
): Promise<{ userId: string }> {
  const user = await new UserRepository().create({ email, password });
  await new EmailService().sendWelcome(user.email);
  await new AuditLogger().log('user_created', user.id);
  return { userId: user.id };
}
```

When `UserRepository`, `EmailService`, or `AuditLogger` internals change, the signature of `registerUser` stays fixed.

### Python — Facade Function/Class

```python
# facade.py — stable surface

from .db.user_repository import UserRepository
from .services.email import EmailService
from .logging.audit import AuditLogger

def register_user(email: str, password: str) -> dict:
    """
    Stable public entry point for user registration.
    Internals may change; this signature will not.
    """
    repo = UserRepository()
    user = repo.create(email=email, password=password)
    EmailService().send_welcome(user.email)
    AuditLogger().log("user_created", user.id)
    return {"user_id": str(user.id)}
```

### Rust — Facade Function/Module

```rust
// src/facade.rs — stable public surface

use crate::db::user_repository::UserRepository;
use crate::services::email::EmailService;
use crate::logging::AuditLogger;

pub struct RegisterResult {
    pub user_id: String,
}

pub async fn register_user(
    email: &str,
    password: &str,
) -> Result<RegisterResult, Box<dyn std::error::Error>> {
    let repo = UserRepository::new();
    let user = repo.create(email, password).await?;
    EmailService::new().send_welcome(&user.email).await?;
    AuditLogger::new().log("user_created", &user.id).await?;
    Ok(RegisterResult { user_id: user.id })
}
```

In `lib.rs`, expose only the facade:

```rust
// src/lib.rs
pub use crate::facade::register_user;
pub use crate::facade::RegisterResult;
// Internal modules are private — not pub
mod db;
mod services;
mod logging;
mod facade;
```

---

## 5. Type Conversion — `From` / `Into`

Converting between old and new types without forcing callers to change.

### TypeScript — Conversion Functions

TypeScript has no standard `From`/`Into` mechanism. Use named conversion functions:

```typescript
// Old type
interface LegacyUser {
  user_name: string;
  user_email: string;
}

// New type
interface User {
  username: string;
  email: string;
}

// Explicit conversion (like From in Rust)
function userFromLegacy(legacy: LegacyUser): User {
  return { username: legacy.user_name, email: legacy.user_email };
}

// Or as a static method
class User {
  username: string;
  email: string;

  static fromLegacy(legacy: LegacyUser): User {
    return Object.assign(new User(), {
      username: legacy.user_name,
      email: legacy.user_email,
    });
  }
}
```

For two-way conversion, use a mapper class:

```typescript
class UserMapper {
  static toLegacy(user: User): LegacyUser {
    return { user_name: user.username, user_email: user.email };
  }
  static fromLegacy(legacy: LegacyUser): User {
    return { username: legacy.user_name, email: legacy.user_email };
  }
}
```

### Python — Conversion Methods / `__init__` Overloads

```python
from dataclasses import dataclass

@dataclass
class LegacyUser:
    user_name: str
    user_email: str

@dataclass
class User:
    username: str
    email: str

    @classmethod
    def from_legacy(cls, legacy: LegacyUser) -> "User":
        return cls(username=legacy.user_name, email=legacy.user_email)

    def to_legacy(self) -> LegacyUser:
        return LegacyUser(user_name=self.username, user_email=self.email)

# Usage:
legacy = LegacyUser(user_name="ada", user_email="ada@example.com")
user = User.from_legacy(legacy)
back = user.to_legacy()
```

### Rust — `From` / `Into` Traits

Implement `From<OldType>` for the new type. The `Into` blanket implementation is automatic.

```rust
#[derive(Debug)]
struct LegacyUser {
    user_name: String,
    user_email: String,
}

#[derive(Debug)]
struct User {
    username: String,
    email: String,
}

// Implement From — automatically gives Into for free
impl From<LegacyUser> for User {
    fn from(legacy: LegacyUser) -> Self {
        User {
            username: legacy.user_name,
            email: legacy.user_email,
        }
    }
}

// Usage:
let legacy = LegacyUser { user_name: "ada".into(), user_email: "ada@example.com".into() };

let user = User::from(legacy);          // explicit From
let user: User = legacy_val.into();     // automatic Into
```

**Fallible conversions**: use `TryFrom`/`TryInto` when the conversion can fail:

```rust
use std::convert::TryFrom;

impl TryFrom<String> for UserId {
    type Error = String;

    fn try_from(s: String) -> Result<Self, Self::Error> {
        if s.is_empty() {
            Err("UserId cannot be empty".to_string())
        } else {
            Ok(UserId(s))
        }
    }
}
```

**Rule**: always implement `From`, never implement `Into` directly (the blanket `impl<T, U: From<T>> Into<U> for T` handles it).

---

## 6. Public API Control — Declaring What Is Public

### TypeScript — `package.json` `exports` Field

The `exports` field precisely controls what paths consumers can import. Without it, any file in the package is importable.

```json
{
  "name": "my-package",
  "version": "1.2.0",
  "main": "./dist/index.js",
  "types": "./dist/index.d.ts",
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "import": "./dist/index.mjs",
      "require": "./dist/index.cjs"
    },
    "./utils": {
      "types": "./dist/utils/index.d.ts",
      "import": "./dist/utils/index.mjs",
      "require": "./dist/utils/index.cjs"
    },
    "./package.json": "./package.json"
  }
}
```

Once `exports` is defined, **only the listed paths are importable**. `import { x } from 'my-package/internal'` fails even if `dist/internal.js` exists.

**Backward-compatible migration** when adding `exports` to an existing package (expose everything that was previously accessible):

```json
{
  "exports": {
    ".": "./dist/index.js",
    "./lib": "./dist/lib/index.js",
    "./lib/*": "./dist/lib/*.js",
    "./package.json": "./package.json"
  }
}
```

**TypeScript `typesVersions`** for supporting multiple TS versions:

```json
{
  "types": "dist/index.d.ts",
  "typesVersions": {
    ">=4.7": { "*": ["dist/ts4.7/*"] },
    "*":     { "*": ["dist/ts4.0/*"] }
  }
}
```

### Python — `__all__` in `__init__.py`

```python
# mypackage/__init__.py

from .user import UserService
from .email import EmailService
from .models import User, UserRecord

# Explicit public API — only these names are exported by `from mypackage import *`
# Also signals to IDEs and type checkers what is intentionally public
__all__ = [
    "UserService",
    "EmailService",
    "User",
    "UserRecord",
]

# Anything not in __all__ is still importable directly, but is signaled as internal
```

**`__all__` does not enforce privacy.** It is a convention that IDEs, linters (pylint, ruff), and `import *` respect. Direct imports of unlisted names still work.

### Rust — Module Visibility

Rust's visibility system is the only one that provides hard enforcement:

```rust
// src/lib.rs

// Public — part of the API
pub mod user;
pub mod email;
pub use crate::models::{User, UserRecord};

// Private — completely inaccessible outside the crate
mod internal;
mod db;

// Crate-only — accessible within the crate, not to consumers
pub(crate) mod utils;

// Module-level re-export hides internal structure
pub use crate::user::UserService;
pub use crate::email::EmailService;
```

Visibility rules:
- `pub` — accessible to everyone
- `pub(crate)` — accessible anywhere in this crate only
- `pub(super)` — accessible in the parent module only
- (no keyword) — private to this module only

---

## 7. Workspace / Monorepo Dependency Wiring

### TypeScript — pnpm Workspace

Root `pnpm-workspace.yaml`:

```yaml
packages:
  - 'packages/*'
  - 'apps/*'
```

Declare cross-package dependencies using `workspace:` protocol in `package.json`:

```json
{
  "name": "@myorg/app",
  "dependencies": {
    "@myorg/shared": "workspace:*",
    "@myorg/utils":  "workspace:^"
  }
}
```

- `workspace:*` resolves to the exact current workspace version. On publish, becomes the exact version (e.g., `"1.5.0"`).
- `workspace:^` resolves to a caret range on publish (e.g., `"^1.5.0"`).
- `workspace:~` resolves to a tilde range on publish.

After `pnpm install`, `@myorg/shared` is symlinked from `node_modules`, so changes to it are immediately visible without rebuilding.

**Bun workspace** (same concept, `package.json` only — no separate yaml):

```json
{
  "name": "myrepo-root",
  "workspaces": ["packages/*", "apps/*"]
}
```

Member `package.json`:

```json
{
  "name": "@myorg/app",
  "dependencies": {
    "@myorg/shared": "workspace:*"
  }
}
```

### TypeScript — `tsconfig.json` Path Aliases

In each package's `tsconfig.json`:

```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@myorg/shared": ["../shared/src/index.ts"],
      "@myorg/shared/*": ["../shared/src/*"],
      "@utils/*": ["src/utils/*"]
    }
  }
}
```

For tests with Vitest, wire the same paths via `vite-tsconfig-paths`:

```bash
pnpm add -D vite-tsconfig-paths
```

```typescript
// vitest.config.ts
import { defineConfig } from 'vitest/config';
import tsconfigPaths from 'vite-tsconfig-paths';

export default defineConfig({
  plugins: [tsconfigPaths()],
  test: {
    // Vitest now resolves @myorg/shared → ../shared/src/index.ts
  },
});
```

### Python — Workspace via pyproject.toml Optional Dependencies

Python does not have a native workspace protocol like pnpm. Use path-based installs in a monorepo:

```toml
# apps/api/pyproject.toml
[project]
name = "my-api"
version = "0.1.0"

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio",
]

[tool.uv.sources]
my-shared = { path = "../../packages/shared", editable = true }
```

With `uv` (recommended) or `pip -e`:

```bash
# Install shared package in editable mode so changes are live
uv pip install -e ../../packages/shared

# Or with pip
pip install -e ../../packages/shared
```

**Extra groups** for optional integrations:

```toml
[project.optional-dependencies]
dev    = ["pytest>=8.0", "ruff", "mypy"]
server = ["fastapi>=0.110", "uvicorn[standard]"]
redis  = ["redis>=5.0"]
all    = ["my-package[server,redis]"]
```

Install a specific extra: `pip install 'my-package[server,redis]'`

### Rust — Cargo Workspace

Root `Cargo.toml` (virtual manifest — no `[package]`):

```toml
[workspace]
members = [
    "crates/core",
    "crates/api",
    "crates/cli",
]
resolver = "3"

[workspace.package]
version     = "0.5.0"
edition     = "2024"
authors     = ["My Team"]
license     = "MIT"
repository  = "https://github.com/myorg/myrepo"

[workspace.dependencies]
serde       = { version = "1.0", features = ["derive"] }
tokio       = { version = "1.0", features = ["full"] }
anyhow      = "1.0"
```

Member crate `crates/api/Cargo.toml`:

```toml
[package]
name    = "my-api"
version.workspace   = true
edition.workspace   = true
authors.workspace   = true

[dependencies]
my-core = { path = "../core" }           # local path dep
serde   = { workspace = true }           # inherits workspace version
tokio   = { workspace = true }           # inherits workspace version + features
anyhow  = { workspace = true }
```

Run across all workspace members:

```bash
cargo test --workspace
cargo build --workspace
cargo check --workspace
```

---

## 8. Feature Flags for Gradual Migration

Allow callers to opt into new behavior while the old behavior remains default.

### TypeScript — Runtime Feature Flags

TypeScript has no compile-time feature flags. Use environment variables or configuration:

```typescript
// config.ts
export const FEATURES = {
  useNewEmailService: process.env.FF_NEW_EMAIL === 'true',
  enableV2Api: process.env.FF_V2_API === 'true',
} as const;

// email-factory.ts
import { FEATURES } from './config';
import { LegacyEmailService } from './legacy';
import { NewEmailService }    from './new';

export function createEmailService() {
  return FEATURES.useNewEmailService
    ? new NewEmailService()
    : new LegacyEmailService();
}
```

For build-time elimination (bundlers):

```typescript
// Only the live branch gets bundled when using tree-shaking
if (process.env.NODE_ENV === 'production') {
  // Dead code elimination removes the else branch
}
```

### Python — Runtime Feature Flags

```python
# features.py
import os

USE_NEW_EMAIL = os.getenv("FF_NEW_EMAIL", "false").lower() == "true"
ENABLE_V2_API = os.getenv("FF_V2_API", "false").lower() == "true"

# email_factory.py
from .features import USE_NEW_EMAIL
from .legacy import LegacyEmailService
from .new import NewEmailService

def create_email_service():
    if USE_NEW_EMAIL:
        return NewEmailService()
    return LegacyEmailService()
```

### Rust — Compile-Time Feature Flags

```toml
# Cargo.toml
[features]
default   = []          # legacy behavior is the default
v2-api    = []          # opt into new API
new-email = []          # opt into new email service
```

```rust
// src/email.rs

#[cfg(not(feature = "new-email"))]
pub fn create_email_service() -> LegacyEmailService {
    LegacyEmailService::new()
}

#[cfg(feature = "new-email")]
pub fn create_email_service() -> NewEmailService {
    NewEmailService::new()
}
```

**Gradual migration path with features:**

```toml
[features]
default       = ["legacy-api"]
legacy-api    = []
v2-api        = []
```

```rust
#[cfg(feature = "legacy-api")]
pub mod v1 {
    pub fn old_endpoint() { /* ... */ }
}

#[cfg(feature = "v2-api")]
pub mod v2 {
    pub fn new_endpoint() { /* ... */ }
}
```

Dependents opt in: `my-lib = { version = "1.0", features = ["v2-api"] }`

When the migration is complete: flip `default = ["v2-api"]`, deprecate `legacy-api`, remove in the next major version.

**Feature flag rules:**
- Features must be additive. Enabling a feature must never remove functionality.
- Features must not change the meaning of existing code, only add to it.
- Violating either rule is a semver-breaking change.

---

## 9. Integration Testing

### TypeScript — Vitest

**Single-package setup:**

```typescript
// vitest.config.ts
import { defineConfig } from 'vitest/config';
import tsconfigPaths from 'vite-tsconfig-paths';

export default defineConfig({
  plugins: [tsconfigPaths()],
  test: {
    globals: true,
    environment: 'node',
  },
});
```

**Integration test (tests the wired-up system, not units):**

```typescript
// tests/integration/user-registration.test.ts
import { describe, it, expect } from 'vitest';
import { registerUser } from '../../src/facade';

describe('User registration integration', () => {
  it('creates user and sends welcome email', async () => {
    const result = await registerUser('test@example.com', 'secret');
    expect(result.userId).toBeDefined();
  });
});
```

**Monorepo setup (Vitest workspace):**

```typescript
// vitest.config.ts (root)
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    projects: ['packages/*'],
  },
});
```

Each `packages/*/vitest.config.ts` can override with package-specific settings.

**Run specific project:**

```bash
vitest --project @myorg/api
```

### Python — pytest

**pyproject.toml test configuration:**

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio",
    "pytest-cov",
]

[tool.pytest.ini_options]
addopts        = ["--import-mode=importlib", "-v"]
testpaths      = ["tests"]
asyncio_mode   = "auto"
```

**`conftest.py` — shared fixtures:**

```python
# tests/conftest.py
import pytest
from mypackage.db import Database
from mypackage.facade import register_user

@pytest.fixture(scope="session")
def db():
    """Real database for integration tests."""
    d = Database.from_env()
    d.migrate()
    yield d
    d.rollback()

@pytest.fixture
def clean_db(db):
    """Per-test database isolation via transaction rollback."""
    with db.transaction() as tx:
        yield tx
        tx.rollback()
```

**Integration test:**

```python
# tests/integration/test_registration.py
import pytest

def test_register_user_creates_record(clean_db):
    result = register_user("test@example.com", "secret")
    assert result["user_id"]
    user = clean_db.query("SELECT * FROM users WHERE id = ?", result["user_id"])
    assert user is not None

def test_deprecated_function_warns():
    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        from mypackage import OldEmailService  # triggers __getattr__ deprecation
        assert any("OldEmailService" in str(warning.message) for warning in w)
```

**Run tests:**

```bash
pytest tests/integration/
pytest -k "test_register"
pytest --tb=short
```

### Rust — `cargo test` Integration Tests

**Directory layout:**

```
my-crate/
├── Cargo.toml
├── src/
│   └── lib.rs        # library code
└── tests/
    ├── common/
    │   └── mod.rs    # shared test helpers (not a test itself)
    └── integration.rs  # integration test file
```

**Shared helpers (`tests/common/mod.rs`):**

```rust
pub fn setup_test_db() -> TestDatabase {
    TestDatabase::connect("postgres://localhost/testdb")
}

pub fn teardown(db: TestDatabase) {
    db.rollback();
}
```

Files in `tests/common/` or any subdirectory are not treated as separate test executables — only top-level files in `tests/` are.

**Integration test (`tests/integration.rs`):**

```rust
// No #[cfg(test)] needed here — Cargo handles it
use my_crate::facade::register_user;

mod common;

#[test]
fn test_register_user_creates_record() {
    let db = common::setup_test_db();
    let result = register_user("test@example.com", "secret").unwrap();
    assert!(!result.user_id.is_empty());
    common::teardown(db);
}

#[test]
fn test_deprecated_fn_still_compiles() {
    // Allow deprecated to suppress warning in test code
    #[allow(deprecated)]
    let _ = my_crate::old_send_email("a@b.com", "hi", "body");
}
```

**Run only integration tests:**

```bash
cargo test --tests                    # all integration tests
cargo test --test integration         # specific file
cargo test --test integration -- test_register  # specific test within file
cargo test --workspace               # all crates in workspace
```

---

## 10. Semver Signaling

How to communicate breaking vs. compatible changes to consumers.

### TypeScript

**`package.json` version field:**

```json
{
  "version": "1.4.2"
}
```

- `1.4.2 → 1.4.3`: patch — bug fix, no API change
- `1.4.2 → 1.5.0`: minor — new exports added, all old exports still present
- `1.4.2 → 2.0.0`: major — removed or changed exports, type incompatibilities

**TypeScript-specific semver rules (semver-ts.org):**

A type change is a breaking change if it causes previously-valid calling code to fail to compile. Examples:

- Removing an exported type or interface → MAJOR
- Narrowing an existing type (adding required property) → MAJOR
- Widening a function parameter type → MINOR (accepting more input)
- Narrowing a function return type → MINOR (returning more specific output)

Use `typesVersions` in `package.json` to ship type definitions for multiple TypeScript versions simultaneously (see Section 6).

**Changesets (recommended for monorepos):**

```bash
pnpm changeset        # describe the change
pnpm changeset version # bump versions
pnpm changeset publish # publish to npm
```

### Python

**`__version__` in `__init__.py`:**

```python
# mypackage/__init__.py
__version__ = "1.4.2"
```

**`pyproject.toml` version:**

```toml
[project]
name    = "my-package"
version = "1.4.2"
```

Keep both in sync. Some tools (`hatch`, `setuptools-scm`) can read one from the other.

**Python PEP 387 deprecation timeline:**

1. Add `DeprecationWarning` in version N.
2. Warning must appear in at least **two minor versions**.
3. Preferred deprecation period: **5 years**.
4. Remove in a major version bump after the deprecation period.

### Rust

**`Cargo.toml` version field:**

```toml
[package]
name    = "my-crate"
version = "1.4.2"
```

**SemVer rules for Rust (from the Cargo Book):**

| Change | Version bump |
|---|---|
| Remove or rename a public item | MAJOR |
| Add a non-defaulted method to a public trait | MAJOR |
| Add fields to a non-`#[non_exhaustive]` struct | MAJOR |
| Add enum variant (no `#[non_exhaustive]`) | MAJOR |
| Add a new public item | MINOR |
| Add enum variant under `#[non_exhaustive]` | MINOR |
| Add defaulted trait method | MINOR |
| Deprecate an item (`#[deprecated]`) | MINOR |
| Bug fix | PATCH |

**`cargo-semver-checks` — automated semver verification:**

```bash
cargo install cargo-semver-checks

# Check current version against what's published on crates.io
cargo semver-checks

# Check against a specific baseline version
cargo semver-checks --baseline-version 1.3.0

# Check in CI (GitHub Actions)
# uses: obi1kenobi/cargo-semver-checks-action@v2
```

`cargo-semver-checks` uses rustdoc JSON output to detect removed items, changed signatures, and other breaking changes automatically.

**`#[non_exhaustive]` — preventing downstream exhaustive pattern matches:**

```rust
#[non_exhaustive]
pub enum Status {
    Active,
    Inactive,
    // Future variants can be added without a MAJOR bump
}

// Consumers MUST use wildcard:
match status {
    Status::Active   => {},
    Status::Inactive => {},
    _ => {},  // required by compiler
}
```

Apply `#[non_exhaustive]` at definition time. Adding it later is a breaking change.

---

## 11. Universal Principles (Language-Agnostic)

These apply regardless of language:

**Never break existing callers.**
If code that worked before your change stops working after it, that is a breaking change. Breaking changes require a major version bump.

**Re-export old names from new locations.**
When a module or class moves, add a re-export at the old path. Remove the re-export only after a proper deprecation period.

**Deprecate before removing.**
The sequence is always: (1) add new thing, (2) mark old thing deprecated pointing at new thing, (3) wait at least one major version, (4) remove old thing.

**The facade stabilizes a surface.**
Never expose internals directly. Everything that crosses a package/crate/module boundary should be a deliberate, named export. This is what lets you refactor freely inside.

**Feature flags are additive.**
A feature flag may add new behavior. It must never remove or change existing behavior. Violating this is a semver-breaking change regardless of the version number.

**Tests live outside the package.**
Integration tests import from the public API, not from internal modules. If your integration test needs to reach inside the package to work, the public API is incomplete.

**Semver is a promise.**
A published version number is a contract with every caller. Tools (`cargo-semver-checks`) can verify Rust automatically. TypeScript and Python require discipline and code review.

---

## Quick Reference Cheat Sheet

| Task | TypeScript | Python | Rust |
|---|---|---|---|
| Re-export from old path | `export { X } from './new'` | `from .new import X` | `pub use crate::new::X;` |
| Alias old name | `export { New as Old } from './new'` | `from .new import New as Old` | `pub use crate::new::New as Old;` |
| Mark deprecated | `/** @deprecated */` + runtime warn | `warnings.warn(..., DeprecationWarning, stacklevel=2)` | `#[deprecated(since="x.y", note="...")]` |
| Deprecated module attribute | N/A | `def __getattr__(name)` in `__init__.py` | `#[deprecated] pub use` (with caveat) |
| Control public API | `exports` in `package.json` | `__all__` in `__init__.py` | `pub` / `pub(crate)` visibility |
| Workspace member wiring | `"dep": "workspace:*"` in `package.json` | `pip install -e ../shared` | `my-dep = { path = "../my-dep" }` |
| Path alias for imports | `paths` in `tsconfig.json` | N/A (use editable installs) | N/A (use `path =` deps) |
| Feature flags | `process.env.FF_X` | `os.getenv("FF_X")` | `#[cfg(feature = "x")]` |
| Integration test location | `tests/` or `src/__tests__/` | `tests/` | `tests/` (top-level, separate crate) |
| Semver check tool | `changeset` / manual | manual + `bump2version` | `cargo semver-checks` |
| Version field location | `package.json` `.version` | `pyproject.toml` + `__version__` | `Cargo.toml` `[package].version` |

---

## Appendix: Known Pitfalls

**TypeScript**: `export *` from a barrel can break tree-shaking. Use explicit `export { X }` for published packages.

**TypeScript**: `@deprecated` JSDoc is IDE-only. There is no runtime enforcement unless you add a `console.warn` manually.

**TypeScript**: The `exports` field in `package.json` is enforced by Node 12+ and bundlers. `main` is the fallback for older Node. Ship both during transition.

**Python**: `DeprecationWarning` is silenced by default in non-`__main__` contexts. Users must run with `-W default` or `PYTHONWARNINGS=default` to see them. Always document this in the changelog.

**Python**: `__all__` does not prevent direct imports. `from mypackage.internal import Secret` still works even if `internal` is not in `__all__`. It is a convention, not enforcement.

**Python 3.13+**: `@warnings.deprecated` is the canonical way to decorate. Before 3.13, use `warnings.warn()` inside the function body with `stacklevel=2`.

**Rust**: `#[deprecated]` on a `pub use` re-export does not reliably emit a warning at the import site (Rust issue #85388). Prefer placing `#[deprecated]` on the original item definition.

**Rust**: `#[non_exhaustive]` cannot be added retroactively without a MAJOR bump. Add it when you first define an enum or struct if you anticipate future variants/fields.

**Rust**: Feature flags are unified across workspace members. If crate A enables `serde/derive` and crate B depends on `serde` without that feature, the workspace build may still have it enabled due to feature unification. Use `resolver = "2"` (or `"3"`) in the workspace root to reduce unintended unification.

**Rust**: `Into` must never be implemented directly. Always implement `From` and get `Into` for free via the blanket impl. Implementing both creates ambiguity and the compiler will refuse.
