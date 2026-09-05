---
description: Check if a URL is safe to fetch
allowed-tools: mcp__safe-fetch__check_url
argument-hint: <url>
---

Check whether the given URL passes the safety policy (domain allowlist, SSRF prevention, blocklist) using the `mcp__safe-fetch__check_url` tool.

URL: $ARGUMENTS

Report the result to the user — whether the URL currently passes the network policy or is blocked, and why; this is not a verdict on content trust.
