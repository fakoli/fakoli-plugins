# nat464-sidecar Code Patterns

## Listener Pattern (TCP Server)

Entry point function that accepts connections in a loop and spawns a handler task per connection.

```rust
use tokio::net::{TcpListener, TcpStream};
use tracing::{debug, error, info};

pub async fn run_<name>(port: u16) -> anyhow::Result<()> {
    let addr = format!("[::]:{port}");
    let listener = TcpListener::bind(&addr).await?;
    info!(listen_addr = %addr, "<name> listening");

    loop {
        let (stream, src_addr) = listener.accept().await?;
        debug!(%src_addr, "accepted connection");

        tokio::spawn(async move {
            if let Err(e) = handle_connection(stream).await {
                error!(%src_addr, error = %e, "connection failed");
            }
        });
    }
}

async fn handle_connection(stream: TcpStream) -> anyhow::Result<()> {
    // Implementation here
    Ok(())
}
```

**Rules:**
- Listen on `[::]` (dual-stack) unless IPv4-only is required
- Error inside `tokio::spawn` — never propagate up to the accept loop
- Use structured tracing fields, not format strings

## Protocol Handler Pattern

Parse/serialize protocol messages on a TCP stream. Return parsed request; let caller handle the connection.

```rust
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::TcpStream;
use tracing::debug;

// Constants at module level
const PROTOCOL_VERSION: u8 = 0x01;

// Parsed request type
#[derive(Debug)]
pub struct ParsedRequest {
    pub field: String,
    pub port: u16,
}

pub async fn parse_request(stream: &mut TcpStream) -> anyhow::Result<ParsedRequest> {
    let version = stream.read_u8().await?;
    if version != PROTOCOL_VERSION {
        anyhow::bail!("unsupported version: {version}");
    }
    // Parse remaining fields...
    debug!(?field, port, "request parsed");
    Ok(ParsedRequest { field, port })
}
```

**Rules:**
- Take `&mut TcpStream`, not owned — caller keeps the stream for relay
- Use `anyhow::bail!` for protocol violations
- Constants in mod.rs (shared across module files)

## Bidirectional Relay Pattern

Forward bytes between two async streams. Used after protocol handshake.

```rust
use tokio::io::{self, AsyncRead, AsyncWrite};
use tracing::debug;

pub async fn bidirectional_copy<A, B>(mut a: A, mut b: B) -> io::Result<(u64, u64)>
where
    A: AsyncRead + AsyncWrite + Unpin,
    B: AsyncRead + AsyncWrite + Unpin,
{
    let result = io::copy_bidirectional(&mut a, &mut b).await;
    if let Ok((up, down)) = &result {
        debug!(up, down, "relay completed");
    }
    result
}
```

## HTTP Server Pattern (hyper)

Lightweight HTTP server for health/metrics endpoints.

```rust
use std::convert::Infallible;
use http_body_util::Full;
use hyper::body::Bytes;
use hyper::server::conn::http1;
use hyper::service::service_fn;
use hyper::{Request, Response, StatusCode};
use hyper_util::rt::TokioIo;
use tokio::net::TcpListener;
use tracing::{error, info};

pub async fn run_http_server(port: u16) -> anyhow::Result<()> {
    let addr = std::net::SocketAddr::from(([0, 0, 0, 0, 0, 0, 0, 0], port));
    let listener = TcpListener::bind(addr).await?;
    info!(%addr, "http server listening");

    loop {
        let (stream, _) = listener.accept().await?;
        let io = TokioIo::new(stream);
        tokio::spawn(async move {
            if let Err(e) = http1::Builder::new()
                .serve_connection(io, service_fn(handle_request))
                .await
            {
                if !e.is_incomplete_message() {
                    error!(error = %e, "http connection error");
                }
            }
        });
    }
}

async fn handle_request(
    req: Request<hyper::body::Incoming>,
) -> Result<Response<Full<Bytes>>, Infallible> {
    match req.uri().path() {
        "/endpoint" => Ok(Response::new(Full::new(Bytes::from("ok")))),
        _ => Ok(Response::builder()
            .status(StatusCode::NOT_FOUND)
            .body(Full::new(Bytes::from("not found")))
            .unwrap()),
    }
}
```

## Test Patterns

### TCP Test Pair Helper

Create connected client/server streams for protocol testing without needing a real server.

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use tokio::io::AsyncWriteExt;
    use tokio::net::TcpListener;

    async fn test_pair() -> (TcpStream, TcpStream) {
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let addr = listener.local_addr().unwrap();
        let client = TcpStream::connect(addr).await.unwrap();
        let (server, _) = listener.accept().await.unwrap();
        (client, server)
    }

    #[tokio::test]
    async fn test_parse_valid_request() {
        let (mut client, mut server) = test_pair().await;

        let client_task = tokio::spawn(async move {
            client.write_all(&[/* protocol bytes */]).await.unwrap();
            client
        });

        let result = parse_request(&mut server).await.unwrap();
        assert_eq!(result.field, "expected");
        client_task.await.unwrap();
    }
}
```

### Server Integration Test

Test a full server by binding to port 0 and connecting to it.

```rust
#[tokio::test]
async fn test_server_endpoint() {
    let listener = TcpListener::bind("[::]:0").await.unwrap();
    let port = listener.local_addr().unwrap().port();

    tokio::spawn(async move {
        // Run server loop using the listener
    });

    let mut stream = tokio::net::TcpStream::connect(format!("127.0.0.1:{port}"))
        .await
        .unwrap();
    stream.write_all(b"request data").await.unwrap();
    let mut buf = vec![0u8; 1024];
    let n = stream.read(&mut buf).await.unwrap();
    let response = String::from_utf8_lossy(&buf[..n]);
    assert!(response.contains("expected"));
}
```

## Error Handling

- `anyhow::Result` for all async functions
- `anyhow::bail!("message: {value}")` for protocol/validation errors
- `thiserror` for typed errors when callers need to match variants
- `ConnectionReset` during relay is silently ignored (expected client disconnect)
- Errors inside `tokio::spawn` are logged with `error!`, never propagated

## Tracing Conventions

| Level | Use For |
|-------|---------|
| `info!` | Server start/stop, major lifecycle events |
| `debug!` | Per-connection events, parsed requests, byte counts |
| `error!` | Failures that need attention |

Always use structured fields: `debug!(%src_addr, port, "message")` not `debug!("message: {}", src_addr)`.

## Module Organization

```
src/<module>/
├── mod.rs       # pub use, constants, shared types
├── primary.rs   # Main entry point (run_* function)
└── helper.rs    # Supporting logic (optional)
```

Register: `pub mod <module>;` in `src/main.rs`.
Wire server: add to `tokio::try_join!` in `main.rs`.
Config: add CLI flags to `config.rs` with `#[arg(long, default_value_t = ...)]`.
