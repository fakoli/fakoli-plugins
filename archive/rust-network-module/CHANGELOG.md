# Changelog

## 1.1.0 (2026-09-05)

- Preserve this archived package with native Codex metadata and Claude support.
- Adapt scaffolding to actual project layout, dependencies, MSRV, errors, and lifecycle instead of assuming nat464 conventions.
- Replace no-op listener/protocol/test templates with bounded task ownership, shutdown/drain behavior, a complete sample wire protocol, and real assertions.
- Add isolated Cargo rendering/compile/Clippy verification with 10 protocol and listener behavior tests, including shutdown, errors, fragmentation, and concurrency.
- Replace outdated pattern skeletons with maintained decision guidance and official upstream references.


## 1.0.0 (2026-02-06)

- Initial release
- Listener, protocol, mod, and test templates
- Full pattern catalog reference (listener, protocol handler, relay, HTTP server)
- Error handling and tracing conventions documentation
