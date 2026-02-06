---
name: rust-network-module
description: "Scaffold new Rust async networking modules for the nat464-sidecar project. Use when adding TCP/UDP listeners, protocol handlers, proxies, or translation modules. Triggers: 'scaffold module', 'add new module', 'create listener', 'create proxy', 'add protocol handler', 'new networking module', 'scaffold UDP', 'add ICMP translation'."
---

# Rust Network Module Scaffolding

Scaffold new async networking modules following nat464-sidecar's established patterns.

## Workflow

### 1. Determine Module Type

| Type | Pattern | Example |
|------|---------|---------|
| **Listener** | Accept connections, spawn handler tasks | `proxy/inbound.rs` |
| **Protocol handler** | Parse/serialize protocol messages | `socks5/handshake.rs` |
| **Relay/proxy** | Bidirectional byte forwarding between streams | `proxy/copy.rs`, `socks5/relay.rs` |
| **Resolver/racer** | DNS resolution, connection racing | `happy_eyeballs/resolver.rs`, `racer.rs` |
| **HTTP server** | Hyper-based HTTP endpoint | `health.rs` |

### 2. Create Module Files

Every module is a directory under `src/` with `mod.rs` + implementation files.

```
src/<module_name>/
├── mod.rs           # Re-exports, shared types/constants
├── <primary>.rs     # Main logic
└── (optional).rs    # Additional files as needed
```

Register in parent: add `pub mod <module_name>;` to `src/main.rs` or parent `mod.rs`.

### 3. Apply Project Conventions

See [references/patterns.md](references/patterns.md) for the full pattern catalog with code templates.

**Key conventions:**
- `pub async fn run_<name>(port: u16, ...) -> anyhow::Result<()>` for server entry points
- `tokio::spawn` per connection, errors logged inside spawn (never crash the server)
- `tracing` structured fields: `debug!` per-connection, `info!` lifecycle, `error!` failures
- `anyhow::Result` everywhere, `anyhow::bail!` for protocol errors
- In-module `#[cfg(test)] mod tests` with `test_pair()` helper for TCP stream pairs
- Tests bind to port 0 for random allocation

### 4. Add to Cargo.toml If Needed

Only add dependencies if the new module requires crates not already in Cargo.toml. Current deps: `tokio`, `clap`, `tracing`, `tracing-subscriber`, `hyper`, `hyper-util`, `http-body-util`, `tokio-util`, `anyhow`, `thiserror`.

### 5. Wire Into main.rs

Add the new server to `tokio::try_join!` in `main.rs` if it runs as a long-lived server. Add CLI flags to `config.rs` if the module needs configuration.

### 6. Verify

```bash
cargo build          # Compiles
cargo test           # All tests pass
cargo clippy -- -W clippy::all  # No new warnings
```

## Module Templates

Use the asset templates as starting points:

| Template | Use For |
|----------|---------|
| `assets/listener.rs.tmpl` | TCP/UDP listener with spawn-per-connection |
| `assets/protocol.rs.tmpl` | Protocol parser with handshake + types |
| `assets/mod.rs.tmpl` | Module root with constants and re-exports |
| `assets/tests.rs.tmpl` | Test block with `test_pair()` helper |
