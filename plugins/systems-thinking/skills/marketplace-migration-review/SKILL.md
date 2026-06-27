---
name: Marketplace Migration Review
description: >
  Review a plugin, skill bundle, or agent workflow that has been moved from a standalone
  repository into a marketplace layout. Use this when you need to verify path rewrites,
  manifest identity, registry metadata, changelog/version drift, hook runtime assumptions,
  copied assets, tests, examples, utilities, and migration notes before publishing a
  marketplace package. Ask for a "marketplace migration review", "plugin import audit",
  "path adaptation check", or "marketplace readiness review" to use this workflow.
---

# Marketplace Migration Review

## When to Use

Use Marketplace Migration Review when:

- A plugin, agent bundle, or skill set has been copied from a standalone repository into a marketplace repository.
- You need to confirm that manifests, agent definitions, skills, hooks, tests, utilities, examples, and assets still resolve from the new location.
- You need a compact readiness report before publishing or merging a marketplace plugin change.
- A migration has subtle old-to-new path assumptions, such as `.claude/agents/` becoming `agents/` or `reference/` becoming a plugin-local path.

Do **not** use Marketplace Migration Review when:

- You only need to evaluate a system architecture or vendor proposal. Use `complexity-mapper` or `architecture-risk-review` instead.
- You are creating a new product requirements document. This skill reviews migration integrity, not product scope.
- There is no source layout to compare against and no migration assumptions to inspect.

## Inputs Required

| Input | Required | Description |
| --- | --- | --- |
| Marketplace plugin path | Yes | The destination plugin directory, such as `plugins/systems-thinking`. |
| Source layout or provenance | No | A local upstream checkout, archive, or documented source repository. Strongly recommended when checking dropped files or asset parity. |
| Migration record | No | A `MIGRATION.md`, release note, or PR description that claims which paths and assumptions were adapted. |
| Validation commands | No | Repo-specific validation, registry drift, changelog, and test commands that should pass before publishing. |
| Known exclusions | No | Files intentionally not imported, such as standalone CI workflows, setup scripts, or source-repo scaffolding. |

## Process Steps

### Step 1: Build the Migration Inventory

Run `doc-indexer` over the source layout, destination plugin layout, and any migration record. Produce an inventory that separates:

1. Runtime definitions: manifests, agents, skills, hooks, commands, settings.
2. Supporting material: docs, specs, references, examples, fixtures, utilities, assets.
3. Repository scaffolding: CI workflows, setup scripts, lint config, package metadata, registry output.

Record source and destination paths for every runtime definition and any supporting material that is referenced by runtime definitions.

### Step 2: Check Manifest And Registry Identity

Inspect marketplace metadata and compare it with upstream identity assumptions:

- Plugin manifest name, version, repository URL, license, keywords, and description.
- Marketplace aggregate files such as root marketplace metadata and registry indexes.
- Version markers such as `VERSION`, package metadata, lockfiles, and changelog headings.
- Install instructions and README identity references.

Flag any identity split where runtime names, docs, hooks, tests, or registry metadata disagree.

### Step 3: Trace Path Adaptations

Use `doc-reader` and `caveat-extractor` to trace every path or runtime assumption that changed during import:

- Agent definition directories, tool frontmatter, and agent invocation names.
- Skill references to `reference/`, examples, prompts, vendor docs, previous designs, or output contracts.
- Hook command paths, environment variables, payload fields, transcript matching, and plugin invocation prefixes.
- Utility imports, path discovery, CLI help text, and generated output locations.
- Test fixture paths, eval harness paths, assets, README image links, and examples.

Every adapted path should have an explicit old-to-new mapping in the migration record or PR evidence. If the migration record is missing a mapping, list it as a gap.

### Step 4: Verify Behavior And Evidence

Run the available deterministic checks from the marketplace repository root. Prefer the repository's own scripts when available:

```bash
./scripts/validate.sh plugins/<plugin-name>
./scripts/test-path-resolution.sh plugins/<plugin-name>
./scripts/check-changelogs.sh
./scripts/check-registry-drift.sh
(cd plugins/<plugin-name> && uv run pytest tests -q)
```

If the full test suite intentionally excludes evals or slow tests by default, state that clearly and include the collection count or marker behavior.

### Step 5: Synthesize A Readiness Report

Pass the inventory, path trace, validation output, and unresolved gaps to `synthesis-brief-writer`. The final report should distinguish confirmed evidence from inferred readiness.

## Output Format

Produce a **Marketplace Migration Review**:

```markdown
## Marketplace Migration Review

### Executive Summary
[3-5 sentences covering readiness, main risks, and whether publication is recommended]

### Migration Inventory
| Area | Source Location | Marketplace Location | Status |
| --- | --- | --- | --- |
| Manifest | [path] | [path] | [preserved/adapted/missing] |

### Adaptation Map
| Adapted Assumption | Original | Marketplace | Evidence |
| --- | --- | --- | --- |
| [Example: agent directory] | [.claude/agents] | [agents] | [file/line or command] |

### Validation Results
| Command | Result | Notes |
| --- | --- | --- |
| [command] | [pass/fail/not run] | [important output or limitation] |

### Gaps And Risks
- [Gap]: [why it matters, source anchor, recommended action]

### Recommendation
[Ship / ship with caveats / block], with next actions in priority order.
```

## Failure Modes and Caution Points

| Failure Mode | Signal | Response |
| --- | --- | --- |
| Source layout unavailable | No upstream checkout or archive exists for comparison | Review destination consistency and migration record, but label dropped-file confidence as limited. |
| Migration record is too vague | It lists categories but not concrete old-to-new paths | Treat this as a documentation gap and require explicit mappings for runtime definitions. |
| Registry drift | Manifest version differs from registry, lockfile, or changelog | Regenerate registry metadata and align version markers before publishing. |
| Hook runtime mismatch | Hook JSON points to stale paths or old payload field names | Verify against current hook payload schema and run hook-focused tests. |
| Tests pass only from repo root | Tests fail when run from the plugin directory | Fix relative paths or project metadata so the plugin validates from `plugins/<plugin-name>`. |
| Asset parity assumed but not checked | Image or binary files exist but were not checksummed | Compare file lists and checksums before declaring assets preserved. |

## Related Agents

- `doc-indexer` maps the source and marketplace layouts.
- `doc-reader` extracts concrete path and runtime assumptions.
- `caveat-extractor` identifies stale paths, missing evidence, and hidden assumptions.
- `architecture-dependency-mapper` can map runtime dependencies when hooks, utilities, and tests interact.
- `synthesis-brief-writer` turns the evidence into the final readiness report.
