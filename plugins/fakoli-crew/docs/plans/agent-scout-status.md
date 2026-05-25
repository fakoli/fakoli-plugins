# Agent Frontmatter Schema Verification

Researched: 2026-05-25
Sources:
- https://code.claude.com/docs/en/sub-agents
- https://code.claude.com/docs/en/plugins-reference

## Question 1: `tools:` vs `allowed-tools:` — which is canonical?

**Finding: `tools:` is the official field. `allowed-tools:` is not documented.**

The official "Supported frontmatter fields" table in the sub-agents docs
(https://code.claude.com/docs/en/sub-agents#supported-frontmatter-fields) lists
`tools` with this description:

> "Tools the subagent can use. Inherits all tools if omitted."

Every example in the docs uses `tools:`, never `allowed-tools:`. Specific
examples from the live docs:

```yaml
# From the "safe-researcher" example in sub-agents docs:
---
name: safe-researcher
description: Research agent with restricted capabilities
tools: Read, Grep, Glob, Bash
---
```

```yaml
# From the CLI --agents flag documentation:
claude --agents '{
  "code-reviewer": {
    "tools": ["Read", "Grep", "Glob", "Bash"],
    "model": "sonnet"
  }
}'
```

The plugins-reference page also confirms under the Agents section:

> "Plugin agents support `name`, `description`, `model`, `effort`, `maxTurns`,
> `tools`, `disallowedTools`, `skills`, `memory`, `background`, and `isolation`
> frontmatter fields."

**`allowed-tools:` does not appear anywhere in either documentation page.**

### What this means for fakoli-crew

All 8 agents currently use `allowed-tools:` in their frontmatter. This field is
not in the documented schema. Claude Code may silently ignore it, meaning the
agents currently have **no tool restrictions at all** (they inherit all tools,
which is the documented behavior when `tools:` is omitted).

**Recommendation: rename `allowed-tools:` to `tools:` in all 8 agent files.**
This is a correctness fix, not a style preference — the current field name is
unrecognized.

The companion field for a denylist is `disallowedTools:` (camelCase, documented
in both pages). Do not confuse it with `allowed-tools:`.

---

## Question 2: `model: inherit` — is it officially supported?

**Finding: `model: inherit` is explicitly documented and is the default.**

From the sub-agents docs, the `model` field description:

> "Model to use: `sonnet`, `opus`, `haiku`, a full model ID (for example,
> `claude-opus-4-7`), or `inherit`. Defaults to `inherit`."

From the "Choose a model" section:

> "**inherit**: Use the same model as the main conversation"
> "**Omitted**: If not specified, defaults to `inherit` (uses the same model as
> the main conversation)"

The `code-reviewer` example in the docs explicitly demonstrates it:

```yaml
---
name: code-reviewer
description: Expert code review specialist. ...
tools: Read, Grep, Glob, Bash
model: inherit
---
```

**`model: inherit` is fully supported. All 8 fakoli-crew agents use
`model: sonnet` which is also valid.** No change needed there unless the design
intent is to inherit the caller's model.

### All accepted model values (as of 2026-05-25)

| Value | Meaning |
|-------|---------|
| `sonnet` | Alias for current Sonnet release |
| `opus` | Alias for current Opus release |
| `haiku` | Alias for current Haiku release |
| `claude-opus-4-7` | Full model ID (same values as `--model` flag) |
| `claude-sonnet-4-6` | Full model ID |
| `inherit` | Use main conversation's model (default when omitted) |

---

## Question 3: Color palette — are `orange` and `purple` accepted?

**Finding: Both `orange` and `purple` are officially documented. Neither is
rejected.**

From the sub-agents docs, the `color` field row in the frontmatter table:

> "Display color for the subagent in the task list and transcript. Accepts
> `red`, `blue`, `green`, `yellow`, `purple`, `orange`, `pink`, or `cyan`"

The complete documented palette is:

```
red | blue | green | yellow | purple | orange | pink | cyan
```

**Both `orange` (used by sentinel) and `purple` (used by keeper) are in the
official list.** The prior review that flagged these as problematic was based on
stale or incorrect information. No change is needed.

Note: `magenta` (used by herald) is NOT in this list. `pink` is listed instead.
This is the only color in the current agents that is undocumented:
- `guido`: blue — OK
- `smith`: green — OK
- `welder`: yellow — OK
- `critic`: red — OK
- `scout`: cyan — OK
- `herald`: **magenta** — NOT in the documented palette
- `keeper`: purple — OK
- `sentinel`: orange — OK

`magenta` may still render (the docs do not say unrecognized values are errors),
but it is undocumented. The closest documented value is `pink`. This is a minor
finding; Task 7 should decide whether to change it.

---

## Summary of Required vs Optional Changes

| Agent field | Current state | Required change? | Evidence |
|-------------|---------------|-----------------|---------|
| `allowed-tools:` | Used in all 8 agents | **YES — rename to `tools:`** | Not in schema; `tools:` is the documented field |
| `model: sonnet` | Used in all 8 agents | No | `sonnet` is a valid alias |
| `model: inherit` | Not used | N/A | Documented and valid, but not currently used |
| `color: orange` | sentinel | No | Explicitly in the documented palette |
| `color: purple` | keeper | No | Explicitly in the documented palette |
| `color: magenta` | herald | Optional | `magenta` is not in the documented palette; `pink` is the closest |

---

## Prior Review Assessment

The two prior reviews that claimed `tools:` is the correct field were **correct**
about the field name. The reviews that claimed `model: inherit` is correct were
also accurate — it is documented. The claims about `orange` and `purple` being
rejected were **incorrect**; both are in the official palette.

The core actionable finding is: **all 8 agent files need `allowed-tools:` renamed
to `tools:`** because `allowed-tools:` is not a recognized frontmatter field and
Claude Code silently ignores unrecognized fields, leaving the agents with no tool
restrictions.

Status: COMPLETE
