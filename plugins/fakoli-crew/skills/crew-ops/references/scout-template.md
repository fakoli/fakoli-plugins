# Scout Output Template

Scout's reference files are consumed by implementation agents (guido, welder) that
need exact facts, not prose. Every scout reference follows this structure so
downstream agents never re-parse a novel format. Copy it, fill it, delete sections
that genuinely don't apply (say "N/A — <why>" rather than omitting silently).

```markdown
# <Service Name> API Reference

**Researched:** <YYYY-MM-DD>
**Docs:** <canonical docs URL>
**Status:** Live | Beta | Deprecated (sunset <date>)

Every fact below is marked VERIFIED (observed this session — cite how) or
DOCUMENTED (the docs claim it, not independently confirmed).

## Authentication
- Scheme: <e.g. Bearer token in Authorization header>  [VERIFIED via curl -sI | DOCUMENTED]
- Token source: <where the user gets one>
- Free tier: <limits, or "none">

## Endpoints

### <METHOD> <path>
- Purpose: <one line>
- Auth: <required scheme>
- Request: <body schema or params — exact field names and types>
- Response: <schema with field types; include ONE real abbreviated example>
- Status codes: <code → meaning, especially error semantics>
- Rate limit: <per-endpoint if documented>

(repeat per endpoint; order by integration priority, not docs order)

## Pricing
<unit prices with units made explicit — per request / per 1K chars / per minute>

## Rate Limits & Quotas
<global limits, burst behavior, retry-after semantics>

## Breaking Changes & Deprecations
<dated list from the changelog, or "None documented as of <date>">

## Code Example
One minimal working example in the project's language. State whether it was
RUN (paste the trimmed output) or UNTESTED (and why — e.g. requires paid key).

## Open Questions
What the docs leave ambiguous — flag these instead of guessing.
```

Rules:
- Exact strings over paraphrase: header names, field names, enum values verbatim.
- Mark VERIFIED vs DOCUMENTED on every load-bearing fact (auth format, endpoint
  liveness, pricing) — implementation agents weigh them differently.
- One reference file per service, updated in place — never fork a second copy.
