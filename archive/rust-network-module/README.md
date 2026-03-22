# Rust Network Module

Scaffold new Rust async networking modules following the [nat464-sidecar](https://github.com/fakoli/nat464-sidecar) project's established patterns.

## What It Does

Provides templates and a structured workflow for creating new networking modules with Tokio, tracing, and anyhow. Covers common patterns: TCP/UDP listeners, protocol handlers, bidirectional relays, and HTTP servers.

## Module Types

| Type | Pattern | Template |
|------|---------|----------|
| Listener | Accept connections, spawn handlers | `listener.rs.tmpl` |
| Protocol handler | Parse/serialize messages | `protocol.rs.tmpl` |
| Relay/proxy | Bidirectional byte forwarding | (use patterns.md) |
| HTTP server | Hyper-based endpoint | (use patterns.md) |

## Templates

- `assets/listener.rs.tmpl` - TCP/UDP listener with spawn-per-connection
- `assets/protocol.rs.tmpl` - Protocol parser with handshake and types
- `assets/mod.rs.tmpl` - Module root with constants and re-exports
- `assets/tests.rs.tmpl` - Test block with `test_pair()` helper

## Conventions

- Entry points: `pub async fn run_<name>(port: u16, ...) -> anyhow::Result<()>`
- Per-connection `tokio::spawn`, errors logged inside (never crash the server)
- Structured tracing: `debug!` per-connection, `info!` lifecycle, `error!` failures
- In-module `#[cfg(test)]` tests binding to port 0

## Usage

Invoke the skill when adding modules to nat464-sidecar:

```
/rust-network-module
```

Or trigger naturally: "scaffold module", "add new module", "create listener".

## License

MIT
