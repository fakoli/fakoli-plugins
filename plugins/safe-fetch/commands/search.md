---
description: Search the web with sanitized results
allowed-tools: mcp__safe-fetch__search
argument-hint: <query>
---

Search the web for the user's query using the `mcp__safe-fetch__search` tool. Results are sanitized to remove prompt injection vectors.

Query: $ARGUMENTS

Present the search results to the user. If they want to read a specific result in detail, suggest using `/fetch <url>` to retrieve the full sanitized content.
