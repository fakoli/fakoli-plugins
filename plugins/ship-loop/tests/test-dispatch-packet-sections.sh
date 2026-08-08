#!/usr/bin/env bash
#
# The dispatch-packet skill is a generator: its template defines the packet's
# section set, and its worked example is supposed to instantiate exactly that
# set. When the two drift, every packet generated from the skill inherits a
# section the executor was never told to fill (adversarial review of PR #147
# found four such drifts). Nothing else in the repo can see this, so check it
# here: the template skeleton's headings must equal the example packet's
# headings, in order.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/../skills/dispatch-packet" && pwd)"
TEMPLATE="$SKILL_DIR/references/packet-template.md"
EXAMPLE="$SKILL_DIR/references/example-packet-377.md"

pass=0; fail=0
check() {
  local label="$1" expected="$2" actual="$3"
  if [[ "$expected" == "$actual" ]]; then
    echo "ok - $label"; pass=$((pass+1))
  else
    echo "FAIL - $label"
    echo "  expected: $expected"
    echo "  actual:   $actual"
    fail=$((fail+1))
  fi
}

# Section names only: strip the parenthetical guidance the template carries in
# its headings ("## Why (one incident ...)" -> "Why") so the example is free to
# render a heading without the instructions baked into it.
section_names() {
  sed -n 's/^## \([^(]*\).*/\1/p' | sed 's/[[:space:]]*$//'
}

# The template's skeleton is the fenced block; its prose sections ("Section
# notes", "Which model gets this packet") are documentation, not packet
# sections, and stop at the closing fence.
template_sections="$(sed -n '/^```markdown$/,/^```$/p' "$TEMPLATE" | section_names)"

# The example wraps its packet in a four-backtick fence because the packet body
# itself contains fenced command blocks.
example_sections="$(sed -n '/^````markdown$/,/^````$/p' "$EXAMPLE" | section_names)"

# Guard against the vacuous pass: if a fence marker changes and both extractions
# come back empty, the set-equality check below would "match" on two empty lists.
check "template skeleton exposes its sections" \
  "Context reads" "$(echo "$template_sections" | head -1)"
check "example packet exposes its sections" \
  "Context reads" "$(echo "$example_sections" | head -1)"
check "example section set and order match the template" \
  "$template_sections" "$example_sections"

# Rules the skill states about its own artifacts, which the exemplar must obey.
grep -q '^If blocked for more than ~5 tool calls' "$TEMPLATE" \
  && echo "ok - template carries the stop-and-report anti-stall line" && pass=$((pass+1)) \
  || { echo "FAIL - template is missing the stop-and-report anti-stall line"; fail=$((fail+1)); }

grep -q '^If blocked for more than ~5 tool calls' "$EXAMPLE" \
  && echo "ok - example carries the stop-and-report anti-stall line" && pass=$((pass+1)) \
  || { echo "FAIL - example is missing the stop-and-report anti-stall line"; fail=$((fail+1)); }

grep -q '^MODEL TIER:' "$EXAMPLE" \
  && echo "ok - example records a model tier" && pass=$((pass+1)) \
  || { echo "FAIL - example does not record a model tier"; fail=$((fail+1)); }

echo
echo "passed: $pass  failed: $fail"
[[ $fail -eq 0 ]]
