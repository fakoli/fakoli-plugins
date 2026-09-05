# Choosing networking patterns

This package began as nat464-specific guidance and was archived from the general marketplace. Treat its templates as adaptable examples, not evidence of the target project's current architecture.

## TCP listeners and lifecycle

Bind a `TcpListener` in the caller and pass it to the loop. This lets configuration choose interface/address family and lets tests bind loopback port 0. Do not assume an IPv6 wildcard also accepts IPv4: OS/socket `IPV6_V6ONLY` behavior varies. When strict socket options are required, follow the crate's existing socket builder before constructing the Tokio listener.

The provided listener accepts an injected async handler, shutdown future, maximum connection count, and drain deadline. Its `JoinSet` observes completion and panics, bounds active handlers, and stops accepting on shutdown. Ordinary per-client I/O errors are logged; listener errors and task panics return errors. After the drain period, it aborts and joins remaining tasks. Choose whether abort after the deadline is an expected shutdown outcome or an error for your real service; the example returns success with a warning.

Handlers must be cooperative async tasks. Timeouts and aborts cannot interrupt CPU loops or blocking system calls inside async tasks. Use the existing project's strategy for blocking work. Long-lived servers often need bounded backoff for transient accept failures such as resource exhaustion; the example returns those errors so the caller can apply its policy. A limited active count does not remove the OS listen backlog; choose explicit load shedding when needed.

Use the application's existing shutdown signal/token/task tracker. Do not install a new global Ctrl-C handler inside each module. If the project already uses `CancellationToken`/`TaskTracker`, adapt to those instead of adding a parallel lifecycle. Do not detach handler tasks whose errors or shutdown you need to observe.

## Protocol framing

The shipped protocol demonstrates one version byte plus a two-byte nonzero port in network byte order, followed by a two-byte version/status reply. It is a runnable example, not a production protocol or SOCKS5 implementation. Replace it with the actual wire specification and interoperability fixtures.

Generic `AsyncRead`/`AsyncWrite` enables duplex-stream tests without a socket. Define maximum variable-length fields before allocation, reject unsupported values, preserve endianness, and distinguish protocol rejection from I/O failure using the crate's error conventions. Bound the entire handshake. Tokio's partial reads can consume bytes before cancellation; after timeout/error, close the example stream rather than retrying the parser from byte zero. For a resumable parser, keep explicit framing state.

The included tests exercise actual parsing/reply bytes and invalid/truncated inputs, fragmented delivery, timeout, and broken writers. Adapt the assertions with the wire format; retaining tests for obsolete example bytes does not validate a different protocol.

## Relays, UDP, DNS, and HTTP

- **TCP relay:** Tokio `copy_bidirectional` supports half-close propagation. Test both directions, EOF/half-close, write failures, and shutdown. Do not blanket-ignore `ConnectionReset`; decide whether partial transfer matters to callers.
- **UDP:** use `UdpSocket`, preserve datagram boundaries, define truncation/size policy and peer mapping lifetime. A TCP accept loop is not a UDP implementation. Test empty datagrams, oversized/truncated input, reply destination, and expiration.
- **DNS/connection racing:** use the target project's resolver and address policy; bound attempts, cancel losers, and preserve useful errors. Inject resolution/dialing for deterministic tests rather than depending on public DNS or internet endpoints.
- **HTTP:** inspect the installed Hyper major version and framework first. Hyper 1 uses `Incoming`, body implementations, and runtime adapters differently from Hyper 0.14. Use framework graceful-shutdown support and test real request/status/body behavior, not a generic skeleton.

## Verification

Use `cargo metadata --no-deps` and actual manifests to select package/features. Match the repository's toolchain and check commands. Typical checks are `cargo fmt --all -- --check`, package-scoped `cargo test`, and `cargo clippy --all-targets`; use `--locked` when the repository's lockfile policy requires it. Avoid `--all-features` for mutually exclusive feature sets.

Wrap network tests in a deadline, bind loopback port 0, coordinate readiness with channels/listener ownership, and await spawned tasks. Test protocol success and refusal, malformed input/EOF, I/O errors, stalled peers, bounded concurrency, and shutdown relevant to the actual implementation.

## Official upstream sources reviewed 2026-09-05

- [Tokio graceful shutdown](https://tokio.rs/tokio/topics/shutdown): shutdown consists of detecting, signalling, and awaiting completion; this informed caller-owned shutdown and draining.
- [Tokio JoinSet](https://docs.rs/tokio/latest/tokio/task/struct.JoinSet.html): tracks tasks, observes results, and aborts tracked tasks on drop; used instead of detached per-connection spawning.
- [Tokio TcpListener](https://docs.rs/tokio/latest/tokio/net/struct.TcpListener.html): caller-controlled bind/accept and cancellation semantics.
- [Tokio AsyncReadExt](https://docs.rs/tokio/latest/tokio/io/trait.AsyncReadExt.html): partial-read/cancellation behavior informs parser timeout handling.
- [Cargo test](https://doc.rust-lang.org/cargo/commands/cargo-test.html): package/features/lock/offline selection should follow the actual workspace.

Verify APIs against the target lockfile/toolchain, not whichever release the `latest` documentation points to.
