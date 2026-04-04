# Getting Started with Fakoli Crew

## Installation

```bash
claude plugin install fakoli-crew
```

## Your First Agent

The simplest way to start is with a single agent:

```
/agent:critic Review the authentication module for security issues.
```

The critic will read every file in scope, then produce a structured report with MUST FIX / SHOULD FIX / CONSIDER findings.

## Your First Crew

When a task spans multiple concerns, use a crew:

```
/agent:guido Design an interface for the new payment processor.
```
Wait for guido to finish, then:
```
/agent:welder Wire the new interface into the existing checkout flow.
```
Then:
```
/agent:critic Review the integration for correctness and backward compatibility.
```

## The Critic Gate Pattern

The most impactful workflow discovery from real-world use:

**Run critic after every code write.**

In the BAARA Next project (10-package monorepo, 44K lines), running critic after each build wave caught:
- 10 MUST FIX bugs in Phase 1 (state machine violations, broken API contracts, security holes)
- 5 MUST FIX bugs in Phase 4 (wrong HTTP methods, missing SSE fields, phantom imports)
- 4 MUST FIX bugs in Phase 5 (migration data corruption, missing schemas)

Total: 19 runtime bugs caught before they ever ran. The cost of a critic pass is ~2 minutes. The cost of debugging a compounded state machine violation is hours.

## Model Selection

All agents default to `model: sonnet` in their frontmatter. For maximum capability:
- Use **Sonnet 4.6** for most agents (fast, reliable)
- Use **Opus 4.6** for critic on large codebases (deeper analysis, more context)
