# Hooks v1

## Recommendation

Use hooks sparingly in v1.

## Hook 1: Pre-flight reminder

### Purpose

Remind the main workflow to separate extraction from synthesis.

### Suggested behavior

Before a complex workflow begins, remind the system to:

- assign extraction tasks first
- preserve source anchors
- avoid collapsing evidence and inference too early

## Hook 2: Completion quality check

### Purpose

Check whether the final output includes the minimum decision-quality sections.

### Suggested behavior

Before final completion, verify the output contains:

- assumptions
- top risks
- unresolved questions
- recommended next checks

## Prompt wording best practices

- Use explicit approve/block decision language matching the hook output format.
- Do not ask the LLM to "review the response you just produced" — this triggers file-access attempts in the hook execution environment. Instead, state evaluation criteria directly.
- Scope prompts to the plugin's domain (e.g., "architecture or infrastructure analysis") so non-relevant responses auto-approve.
- Keep prompts under 500 characters.

## If hooks feel brittle

Document them as future work instead of forcing them into v1.
