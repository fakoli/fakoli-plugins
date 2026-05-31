#!/usr/bin/env bash
# run.sh — critic false-pass harness for SL-2 (docs/roadmap.md).
#
# Why this is a printer + scorer, NOT a dispatcher:
#   The critic is a Claude Code subagent (fakoli-state:critic, or
#   fakoli-crew:critic). It can only be dispatched from inside an active Claude
#   Code session via the Agent tool — a bash script cannot spawn a subagent
#   (same constraint as fakoli-crew/tests/test_critics.sh). So the operator runs
#   the critic over each fault case in-session, records the verdict, and this
#   script computes the false-pass rate from the recorded verdicts.
#
# A FALSE PASS = the critic let a known-bad change through. Every case in the
# corpus is an obvious MUST FIX, so any recorded verdict other than "MUST FIX"
# is a false pass.
#
# Usage:
#   bash run.sh --list                 # enumerate cases + expected verdict
#   bash run.sh --score results.tsv    # compute the false-pass rate
#   bash run.sh --template             # print a blank results.tsv to fill in
#   bash run.sh --help
#
# results.tsv format (one line per case; tab- or whitespace-separated):
#   <case-dir-name>    <recorded-verdict>
#   e.g.   01-off-by-one    MUST FIX
#
# Exit codes:
#   0  success
#   2  unknown/missing argument or results file
#   3  results file references an unknown case, or omits a case

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORPUS_DIR="$(cd "${SCRIPT_DIR}/../fixtures/critic-faults" && pwd)"

_cases() {
  # Print case directory names (NN-...), sorted, one per line.
  find "${CORPUS_DIR}" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort
}

_expected_verdict() {
  # Parse the expected verdict from a case's EXPECTED.md.
  local case="$1"
  grep -m1 -oE 'Expected verdict: [A-Z ]+' "${CORPUS_DIR}/${case}/EXPECTED.md" \
    | sed -E 's/^Expected verdict: //' | sed -E 's/[[:space:]]+$//'
}

_normalize() {
  # Uppercase, collapse whitespace — "must fix" -> "MUST FIX".
  printf '%s' "$1" | tr '[:lower:]' '[:upper:]' | tr -s '[:space:]' ' ' \
    | sed -E 's/^ //; s/ $//'
}

_print_help() {
  sed -n '2,40p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

_print_list() {
  printf '\n%-22s %-12s %s\n' "CASE" "EXPECTED" "TASK"
  printf '%-22s %-12s %s\n' "----" "--------" "----"
  local c title
  while IFS= read -r c; do
    title="$(grep -m1 -E '^# Task' "${CORPUS_DIR}/${c}/task.md" | sed -E 's/^# Task [^:]*: //')"
    printf '%-22s %-12s %s\n' "${c}" "$(_expected_verdict "${c}")" "${title}"
  done < <(_cases)
  printf '\nDispatch the critic over each case (see docs/critic-baseline.md), then:\n'
  printf '  bash run.sh --score results.tsv\n\n'
}

_print_template() {
  local c
  while IFS= read -r c; do
    printf '%s\tPASTE_VERDICT_HERE\n' "${c}"
  done < <(_cases)
}

_score() {
  local results="$1"
  if [ ! -s "${results}" ]; then
    printf 'ERROR: results file %s is missing or empty.\n' "${results}" >&2
    return 2
  fi

  local total=0 false_pass=0 caught=0 rc=0
  printf '\n%-22s %-12s %-12s %s\n' "CASE" "EXPECTED" "RECORDED" "OUTCOME"
  printf '%-22s %-12s %-12s %s\n' "----" "--------" "--------" "-------"

  local c expected recorded outcome
  while IFS= read -r c; do
    total=$((total + 1))
    expected="$(_normalize "$(_expected_verdict "${c}")")"
    # Pull the recorded verdict for this case from the results file.
    recorded="$(grep -E "^${c}[[:space:]]" "${results}" | head -n1 \
      | sed -E "s/^${c}[[:space:]]+//")"
    recorded="$(_normalize "${recorded}")"

    if [ -z "${recorded}" ]; then
      outcome="MISSING (counts as false pass)"
      false_pass=$((false_pass + 1))
      rc=3
    elif [ "${recorded}" = "${expected}" ]; then
      outcome="caught"
      caught=$((caught + 1))
    else
      outcome="FALSE PASS"
      false_pass=$((false_pass + 1))
    fi
    printf '%-22s %-12s %-12s %s\n' "${c}" "${expected}" "${recorded:-<none>}" "${outcome}"
  done < <(_cases)

  local rate="n/a"
  if [ "${total}" -gt 0 ]; then
    rate="$(awk "BEGIN { printf \"%.1f%%\", (${false_pass}/${total})*100 }")"
  fi
  printf '\nTotal cases:   %d\n' "${total}"
  printf 'Caught:        %d\n' "${caught}"
  printf 'False passes:  %d\n' "${false_pass}"
  printf 'FALSE-PASS RATE: %s\n\n' "${rate}"
  return "${rc}"
}

main() {
  if [ "$#" -lt 1 ]; then
    _print_help >&2
    return 2
  fi
  case "$1" in
    --list)     _print_list ;;
    --template) _print_template ;;
    --score)
      if [ "$#" -lt 2 ]; then
        printf 'ERROR: --score requires a results file.\n' >&2
        return 2
      fi
      _score "$2"
      ;;
    --help|-h)  _print_help ;;
    *)
      printf 'ERROR: unknown argument %q\n' "$1" >&2
      _print_help >&2
      return 2
      ;;
  esac
}

main "$@"
