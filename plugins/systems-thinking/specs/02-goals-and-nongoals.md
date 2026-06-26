# Goals and Non-Goals

## Goals

- optimize for Claude Code first
- keep the implementation local and file-based
- use small, composable subagents
- write reusable skills in Markdown
- keep extraction separate from synthesis
- preserve source references where possible
- create decision-quality outputs
- avoid over-engineering v1

## Non-goals for v1

- marketplace-ready packaging
- deep Cursor-specific packaging work
- MCP integrations unless clearly necessary
- autonomous long-running systems
- fully polished UI or dashboarding layer
- generalized enterprise workflow engine

## Constraints

- context windows should be protected, not overloaded
- subagents should have narrow, auditable roles
- outputs should surface assumptions and unresolved questions
- the package should feel practical for infrastructure work, not generic AI theater
