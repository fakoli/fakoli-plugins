---
description: Mine coding-agent sessions into local-model eval suites for anvil-serving
allowed-tools: Bash, Read, Write
argument-hint: [retro dir, corpus dir, or session paths]
---

# /session-evals

Use the `session-evals` skill to mine the requested sessions (retro-first
when a post-session-findings corpus exists), curate candidates into
deterministic check-based eval specs, emit them to the eval-data root, and
optionally run them against a local serve.
