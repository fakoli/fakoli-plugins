---
description: Check if a URL is safe to fetch
allowed-tools: mcp__safe-fetch__check_url
argument-hint: <url>
---

Check whether the given URL passes the safety policy (domain allowlist, SSRF prevention, blocklist) using the `mcp__safe-fetch__check_url` tool.

URL: $ARGUMENTS

Report the result to the user — whether the URL is safe or blocked, and why.
