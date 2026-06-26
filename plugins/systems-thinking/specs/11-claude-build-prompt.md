# Claude Build Prompt

Paste the prompt below into Claude Code after customizing it for your repo.

```text
You are helping me design and implement a local Claude Code package for infrastructure and network architecture workflows.

Primary target:
- Claude Code local project usage

Secondary target:
- Cursor compatibility later, only as an adapter or packaging follow-on
- Do not let Cursor-specific uncertainty block the Claude Code implementation

Important operating style:
- Be more aggressive than usual about moving the work forward
- Default to building unless there is a truly blocking ambiguity that would create likely rework
- Do a brief inference and resource-gathering phase before presenting the plan
- Prefer concrete inspection and grounded inference over generic suggestions
- Keep the implementation practical, local, inspectable, and file-based

What I want to build:
A Claude Code package centered on three core workflows for senior infrastructure and network engineering work:

1. Pattern Remix
Definition:
Use prior proven work, target-state goals, and explicit constraints to generate high-quality first drafts and execution plans for new but related problems.

2. Complexity Mapper
Definition:
Gather documentation, architecture assumptions, cost and capacity constraints, operational considerations, and implementation caveats to surface hidden complexity, side effects, risks, dependencies, and likely project blow-up points.

3. Context Sharding
Definition:
Split large bodies of input across smaller parallel subagents so narrower agents can extract structure, summaries, caveats, constraints, and signals before a primary reasoning agent synthesizes them.

Core design intent:
This package should reflect the judgment model of a senior cloud and network engineer who specializes in uncovering hidden implementation complexity.

Implementation requirements:
- Optimize for Claude Code local project structure first
- Use project-level Claude Code conventions unless there is a strong reason not to
- Prefer Markdown-based definitions for subagents and skills
- Use hooks only when they are simple, valuable, and low-risk
- Do not introduce MCP in v1 unless you can clearly justify it
- If Cursor packaging details remain uncertain, document them in COMPATIBILITY_NOTES.md rather than over-designing for them now
- Prefer many small composable files over one giant file

Claude Code-specific expectations:
- Use `.claude/agents/` for subagents unless inspection suggests a better project-local structure
- Use `.claude/settings.json` or another appropriate Claude Code settings file for hooks/config when needed
- Scope tools deliberately for subagents where that improves trust and clarity

I want the package to include these v1 subagents:
1. pattern-remix-planner
2. doc-indexer
3. doc-reader
4. caveat-extractor
5. cost-capacity-analyst
6. architecture-dependency-mapper
7. synthesis-brief-writer

I want these v1 skills/playbooks as Markdown:
1. pattern-remix.md
2. complexity-mapper.md
3. context-sharding.md
4. decision-brief.md
5. architecture-risk-review.md

Possible hooks for v1:
- a pre-flight reminder that extraction and synthesis should be separated
- a completion check that outputs include assumptions, risks, unresolved questions, and recommended follow-ups
Only include hooks if they are straightforward, robust, and justified.
If they feel brittle, stub or document them instead.

Very important: do a short resource and inference phase before the final plan.
Before proposing the package structure, do the following:

Phase 0: Resource and inference pass
- Inspect the current repository thoroughly
- Look for any existing `.claude/` directory, subagents, settings, hooks, prompt files, skills, docs, templates, or related automation
- Look for prior design docs, architecture notes, README patterns, prompt libraries, or examples that suggest how this package should fit into the repo
- Infer what existing conventions, naming patterns, and folder structures are already present
- Identify reusable resources that should be fed into or reflected in the package design
- Summarize what you found and what design implications follow from it

Then continue with:

Phase 1: Discovery and architecture plan
- Propose a file/folder structure optimized for Claude Code
- Explain the architecture of the package
- Identify what belongs in subagents vs skills vs hooks
- Explain any assumptions about how the workflows interact
- List open questions, but do not stop unless they are truly blocking
- Make a recommendation for the minimum viable v1

Phase 2: Scaffold
- Create the folder structure
- Create starter files for subagents, skills, docs, and hooks/config as appropriate
- Write strong first-pass content for each file
- Keep naming human-readable and consistent

Phase 3: Refine
- Tighten prompts and boundaries for each subagent
- Improve consistency across files
- Add usage examples
- Make the README genuinely useful
- Add COMPATIBILITY_NOTES.md for Cursor adaptation if still needed

Behavior rules for subagents:
- Each subagent must have a narrow role
- Extraction-focused agents must extract, not over-synthesize
- Synthesis agents must explicitly call out uncertainty, missing data, assumptions, and unresolved questions
- Where appropriate, outputs should be structured and predictable
- Preserve citations, source pointers, or file references whenever possible

Behavior rules for skills:
- Write each skill as a reusable operating procedure
- For each skill include:
  - when to use it
  - inputs required
  - process steps
  - output format
  - failure modes and caution points

What I want from you right now:
Start with Phase 0 and Phase 1 only.

Deliver:
1. a concise summary of discovered repo resources and conventions
2. inferred design implications
3. a proposed Claude Code-first project structure
4. a package architecture plan
5. a v1 scope recommendation
6. a list of assumptions and any non-blocking open questions

Then pause for approval before scaffolding.
```
