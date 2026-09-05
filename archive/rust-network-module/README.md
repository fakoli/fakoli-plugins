# Rust Network Module

Adaptable examples for Rust async networking modules: a bounded Tokio TCP listener, an executable sample protocol, and meaningful tests. The package was archived from the general marketplace in March 2026 because its original guidance was tied to one internal project. This maintenance release preserves the package without restoring its catalog entry. Native Codex and Claude Code manifests are included.

## Workflow

Invoke `$rust-network-module` in Codex, or select the skill in Claude Code. The skill first inspects the actual repository's manifests, lockfile, MSRV, neighboring code, configuration, and shutdown ownership. It preserves those conventions and adapts the smallest relevant template. It does not require a particular directory layout, error crate, dependency list, or `main.rs` wiring.

Assets live at `skills/rust-network-module/assets/` relative to this package. Resolve them from the installed skill, then write adapted code into the user's project. They are not automatically generated or wired by an installer.

| Template | Behavior |
|---|---|
| `listener.rs.tmpl` | TCP listener provided by caller, injected async handler, maximum active count, shutdown signal, task-error observation, and bounded drain/abort |
| `protocol.rs.tmpl` | Generic async reader/writer example: version + network-order port request; version/status reply |
| `tests.rs.tmpl` | Executable tests for the sample framing, malformed/truncated data, fragmented input, stalls, and writer failure |
| `mod.rs.tmpl` | Optional module root matching the target crate |

Substitute `__NAME__` with snake_case, `__TYPE__` with PascalCase, `__PRIMARY__` with the child module, and `__DESCRIPTION__` with its purpose. Remove unused child modules. The protocol template's wire format is an example, not SOCKS5. TCP templates do not implement UDP, HTTP, ICMP, or DNS racing; [pattern guidance](skills/rust-network-module/references/patterns.md) covers those decisions without promising generated implementations.

## Requirements and lifecycle

The unmodified listener uses Tokio 1 (`rt`, `net`, `macros`, `time`), tracing 0.1, and `std::io::Error::other` (Rust 1.74+). Protocol/tests also need Tokio `io-util`; the package's listener regression tests use `sync`. Tokio's selected release may impose a newer MSRV: preserve the target project's compatible versions/features rather than upgrading blindly. Existing anyhow/thiserror/lifecycle conventions take precedence over these example signatures.

The caller binds an explicit address and owns signals. The listener limits tracked connection tasks, treats a client error separately from listener/task failure, stops accepting on shutdown, and lets handlers finish until a deadline before aborting and joining the remainder. Handlers must cooperate with the async runtime; cancellation cannot interrupt blocking work or CPU loops. The default example treats drain timeout as successful forced shutdown with a warning; adapt that policy to the application.

Protocol parsing has a whole-handshake deadline supplied by the caller. Close/discard partially consumed streams on cancellation unless implementing an explicitly resumable parser. Real implementations must specify their own maximum frame sizes, wire format, error replies, and interoperability requirements.

## Maintainer verification

From this package directory:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

The test renders **all four** templates into a temporary Cargo crate, runs 10 behavior tests, and runs Clippy with warnings denied. It checks TCP exchange, client error recovery, immediate and active-handler shutdown, concurrency limits, forced draining, task panic observation, and protocol success/error/timeout paths. Cargo artifacts remain in the temporary directory. Only ephemeral loopback sockets and in-memory streams are used.

By default Cargo runs offline and needs the corresponding crates already cached. On a fresh developer/CI machine, explicitly allow dependency fetching for the verification fixture:

```bash
NETWORK_TEMPLATE_ALLOW_FETCH=1 python3 -m unittest discover -s tests -p 'test_*.py' -v
```

This fetches Rust packages before offline tests; it does not contact a running service. Do not silently skip the tests when dependencies are unavailable. Validation was performed with Rust 1.96.0, Tokio 1.53.1, and tracing 0.1.44; this is template evidence, not validation against an arbitrary target application's MSRV or protocol.

MIT license.
