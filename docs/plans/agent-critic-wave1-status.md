# Code Review Report — Wave 1 (cli-to-plugin Foundation)

**Scope:**
- `plugins/cli-to-plugin/.claude-plugin/plugin.json`
- `plugins/cli-to-plugin/schemas/help-tree.schema.json`
- `plugins/cli-to-plugin/templates/group-skill.md`
- `plugins/cli-to-plugin/templates/meta-skill.md`
- `plugins/cli-to-plugin/templates/plugin.json.example`
- `docs/plans/2026-05-24-cli-to-plugin.md` (Tasks 1–3, for context)
- `docs/specs/2026-05-24-cli-to-plugin.md` (for contract verification)

**Reviewed by:** critic
**Date:** 2026-05-24

---

## What was verified mechanically

All five files were read in full before any finding was recorded. The following checks were run against live tooling:

- `jsonschema.Draft202012Validator.check_schema` on `help-tree.schema.json` — PASS
- Spec example JSON validated against `help-tree.schema.json` — PASS
- Five broken-input cases (missing `path`, single-element `path`, naked flag, uppercase `cli.name`, non-array `warnings`) — all correctly FAIL
- `plugin.json.example` validated against `schemas/plugin.schema.json` — PASS
- `plugins/cli-to-plugin/.claude-plugin/plugin.json` validated against `schemas/plugin.schema.json` — PASS
- `./scripts/validate.sh plugins/cli-to-plugin` — PASS (4 warnings, 0 errors; warnings are expected for a Wave 1 skeleton)
- Template frontmatter fields validated against `schemas/skill.schema.json` — PASS
- Keyword pattern `^[a-z0-9-]+$` verified for all five manifest keywords — PASS
- Short flag pattern, long flag pattern, `cli.name` pattern — all edge cases correct
- Regex for `--no-pager`, `-R`, `-9bad`, `cli_tool` — all produce expected results

---

## MUST FIX

None.

---

## SHOULD FIX

### 1. Schema has no structural contract for nested command groups

**File:** `plugins/cli-to-plugin/schemas/help-tree.schema.json`

**Issue:** The schema defines `groups[].commands` as an array of leaf `command` objects. There is no `subgroups` field on a group. Deep CLIs like `kubectl` have two levels of grouping: `kubectl create deployment`, `kubectl create service`, etc., where `create` is itself a group whose children are more groups, not leaf commands. Since `additionalProperties` is not set on group items (default: allowed), `discover.py` could silently emit whatever shape it invents for nested groups and the schema would still pass — providing false confidence. Wave 2's `discover.py` implementer will either (a) flatten everything into the top-level `groups` array, or (b) invent a `subgroups` nesting structure, with no schema guidance either way. If they choose differently than Wave 3's test fixtures assume, the fixtures will fail against the schema in a confusing way.

**Fix — Option A (flatten, simpler, matches "one skill per top-level group"):**
Add a description on `groups` items clarifying that nesting is expressed by path length, not by nesting objects:

```json
"groups": {
  "type": "array",
  "description": "Command groups at any depth, flattened. Nesting is expressed via path length, not object nesting. A group at path ['create', 'deployment'] is a sibling of ['pr'] in this array.",
  ...
}
```

**Fix — Option B (add subgroups, richer but complex):**
Add an optional recursive `subgroups` field on group items. Requires a `$ref` to a named `$defs/group` definition.

Option A is strongly preferred given the spec's "one skill per top-level command group" design decision. The implementer needs explicit written guidance that deep paths go into `path: ["create", "deployment"]` on a group, not nested objects. Without this note, the most natural Python code would nest, not flatten.

---

### 2. `meta-skill.md` H1 title does not match `name` frontmatter field

**File:** `plugins/cli-to-plugin/templates/meta-skill.md:5,12`

**Issue:** The frontmatter `name` is `gh-review-and-merge` but the H1 heading is `# Review and merge PRs`. In contrast, `group-skill.md` correctly uses `# gh-pr` for both. The H1 is the human-facing title inside the skill, so some divergence is reasonable — but as a structural template, a future implementer reading this may not know whether to mirror `name` in the H1 or write a prose title. The inconsistency inside the same template set will cause skill generation to produce inconsistent output across per-group and meta-skill files.

**Fix:** Either make the H1 match the name (consistent, mechanical):
```markdown
# gh-review-and-merge
```
Or add a comment on line 13 clarifying the intent:
```markdown
<!-- H1 is prose title — does NOT have to match the frontmatter name -->
# Review and merge PRs
```
The comment approach is better because it teaches downstream agents that this is intentional.

---

### 3. `plugin.json.example` omits `repository` field but does not document why

**File:** `plugins/cli-to-plugin/templates/plugin.json.example`

**Issue:** The spec's "Generated plugin.json" section lists exactly these fields: `name`, `version`, `description`, `author`, `license`, `keywords` — no `repository`. The example correctly matches the spec. However, the example file has no comment explaining that `repository` is intentionally absent (the generated plugin is not a standalone repo; it lives inside wherever the user puts it). When a Wave 2/3 agent is synthesizing the playbook (Task 8), they may add `repository` to the generated manifest, causing a `validate.sh` warning ("license declared but no LICENSE file") cascade, or more precisely passing validation but producing confusing output. A one-line inline comment would lock this in.

**Fix:** Add a comment before the closing brace:
```json
{
  "name": "gh",
  ...
  "keywords": ["gh", "github", "cli", "generated", "cli-to-plugin"]
  // Note: no 'repository' field — the generated plugin has no canonical repo URL.
  // The generator does not know where the user will host it.
}
```
(If JSON comments are undesirable, add a companion `plugin.json.example.md` note, or add a top-of-file HTML comment like the templates use.)

---

## CONSIDER

### 4. `cli.name` pattern allows underscores to fail but does not document that CLIs with underscores in their binary name (e.g., `aws_completer`) will need normalization

**File:** `plugins/cli-to-plugin/schemas/help-tree.schema.json:18`

**Issue:** The pattern `^[a-z0-9][a-z0-9-]*$` correctly rejects underscores. However, `cli.name` is described as "CLI identifier" — if `discover.py` naively sets `cli.name = os.path.basename(binary)`, a binary named `aws_completer` would fail schema validation. The description should say whether `cli.name` is normalized from the binary path or taken verbatim.

**Recommendation:** Update the description to:
```json
"description": "CLI identifier — lowercase, hyphens and digits only. Underscores in binary names must be converted to hyphens (e.g., 'aws-completer' not 'aws_completer')."
```

---

### 5. `discovery.elapsed_ms` has no upper bound — a runaway discovery producing a 64-bit integer is technically valid

**File:** `plugins/cli-to-plugin/schemas/help-tree.schema.json:99`

**Issue:** `elapsed_ms` is typed as `integer, minimum: 0` with no `maximum`. This is unlikely to cause a real bug since `discover.py` has a 30s total timeout, but adding `maximum: 3600000` (1 hour) would make the schema self-documenting about the intended scale.

**Recommendation:** Not a blocker. Add a `maximum` if you want the schema to carry that constraint.

---

### 6. `group-skill.md` "Do NOT use" boundary clause relies on skills that don't exist yet in this template set

**File:** `plugins/cli-to-plugin/templates/group-skill.md:17`

**Issue:** Line 17 references `[[gh-issue]]` and `[[gh-workflow]]` as cross-reference examples in the "When to use" section. These are correct examples for the `gh` CLI. However, the template comment at line 1 only says "NOT a Jinja template — no placeholder substitution" — it doesn't explain that the `[[name]]` links are Claude Code skill cross-references, not markdown links. A future contributor writing skills for a different CLI might not know to use this `[[name]]` syntax or might format them as `[gh-issue](...)` markdown links instead.

**Recommendation:** Add a comment in the template body clarifying the `[[name]]` format:
```markdown
<!-- [[skill-name]] is a Claude Code skill cross-reference, not a markdown link. Use this exact syntax. -->
- Do NOT use for issues or workflow runs — see [[gh-issue]] and [[gh-workflow]].
```

---

## NIT

### 7. `schemas/.gitkeep` is redundant now that `help-tree.schema.json` exists in the directory

**File:** `plugins/cli-to-plugin/schemas/.gitkeep`

`.gitkeep` files exist solely to commit empty directories. The directory now has content. The file is harmless but adds noise to `find` output and `ls` listings.

**Fix:** `git rm plugins/cli-to-plugin/schemas/.gitkeep`

---

### 8. `global_flags` is positioned between `cli` and `groups` in the schema but after `groups` in the spec example

**File:** `plugins/cli-to-plugin/schemas/help-tree.schema.json:40`

The spec example JSON puts `global_flags` after `cli` and before `groups`. The schema property order matches. This is consistent. No action needed — noted only as confirmation that no reordering is required.

---

## What downstream agents have enough of

A Wave 2 `discover.py` implementer has:
- A complete, self-validating JSON Schema with correct `anyOf` for flags, `minItems` constraints, and a `$defs` section they can directly reference in tests.
- A working spec example to validate against during development.
- The `cli.name` pattern to know what normalization is required.
- Clear field-level descriptions for every property.

A Wave 2/3 playbook/synthesis implementer has:
- Concrete `group-skill.md` and `meta-skill.md` templates with all required sections.
- Correct hyphen-form frontmatter keys (not the underscore bug in `templates/basic/`).
- `plugin.json.example` that validates against the marketplace schema.

**What is underspecified for Wave 2:** The flattening vs. nesting decision for deep CLI groups (SHOULD FIX #1 above). This is the only gap that could cause the schema and `discover.py` to diverge without either side knowing, resulting in test fixtures that pass the schema but describe a structure `discover.py` doesn't actually produce.

---

## Verdict: PASS

No MUST FIX findings. The foundation is solid: the manifest validates cleanly against the marketplace schema, the help-tree schema passes its self-check and correctly rejects all broken inputs, the templates use correct hyphen-form frontmatter keys (not the `templates/basic/` bug), both descriptions start with "Use when...", all four required sections are present in each template, and the structural reference comment at the top of each template correctly prevents them from being mistaken for Jinja templates. The one quality gap that could block Wave 2 is the missing guidance on how `discover.py` should represent deep/nested CLI groups — flatten into the top-level array (preferred per the spec's "one skill per top-level group" decision) versus nest objects. This needs to be explicit in the schema description before the `discover.py` agent starts writing code.
