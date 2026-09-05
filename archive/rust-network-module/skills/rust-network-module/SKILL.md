---
name: rust-network-module
description: Add Rust async networking modules with project-adapted listener lifecycle, protocol parsing, and meaningful tests. Includes Tokio TCP and example wire-protocol templates for nat464-sidecar or compatible Rust projects.
---

# Rust Network Module

Start with the actual repository: read its instructions, `Cargo.toml`, lockfile, toolchain/MSRV settings, a neighboring networking module, and existing shutdown/configuration/tests. Preserve the crate's layout, error types, runtime, visibility, feature flags, tracing conventions, and wiring. Do not assume a nat464 dependency list, require directory modules, or register everything in `main.rs`/`try_join!`.

Choose the smallest relevant starting point in [assets](assets/). Resolve these files relative to this installed skill directory, not the user's project. Copy/adapt only the required templates into the requested crate:

| Asset | Purpose |
|---|---|
| `listener.rs.tmpl` | TCP accept loop with caller-owned binding/shutdown, bounded handler count, task observation, and bounded drain |
| `protocol.rs.tmpl` | Executable example framing and parser/reply logic; replace with the actual protocol contract |
| `tests.rs.tmpl` | Assertions for the example protocol's bytes, fragmentation, invalid/truncated input, timeout, and write failure |
| `mod.rs.tmpl` | Optional module root; use a flat file if that matches the project |

Substitute `__NAME__` with a snake_case identifier, `__TYPE__` with a PascalCase type prefix, `__PRIMARY__` with the actual child module, and `__DESCRIPTION__` with its purpose. The example protocol is **not SOCKS5**. TCP assets do not implement UDP, ICMP, DNS racing, or HTTP: use [patterns](references/patterns.md) to choose those architectures without pretending a TCP scaffold implements them.

Implement the requested behavior before claiming completion. Define frame/size limits, deadlines, overload policy, shutdown ownership, and error handling appropriate to the real feature. Keep binding explicit; `[::]` is not a portable guarantee of dual-stack behavior. A handshake interrupted during a partial read must be discarded or resumed from saved state, not blindly restarted.

Wire through the crate's existing lifecycle. Add only missing dependencies/features compatible with its MSRV; template requirements and verification commands are in [the README](../../README.md). Run formatting, the relevant tests, and the project's normal checks. Include observable success, error/protocol, and shutdown paths when implementing a server. Tests use port 0 or in-memory duplex streams and deadlines; empty writes or successful compilation alone do not verify networking behavior.
