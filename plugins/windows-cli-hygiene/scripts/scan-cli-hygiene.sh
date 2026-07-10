#!/usr/bin/env bash
# scan-cli-hygiene.sh — flag Windows/cross-platform CLI hazards in source, the
# deterministic-check class the retro corpus kept re-discovering by hand (the
# scanner form of ship-loop's "Windows/platform discipline"). Advisory: reports
# `file:line: RULE message`, ALWAYS exits 0 — a gate wrapper decides severity.
#
# Hazards flagged:
#   NON_ASCII_OUTPUT  non-ASCII byte in a string headed to stdout (em-dash /
#                     arrow / ✎) — crashes a cp1252 Windows console with
#                     UnicodeEncodeError.
#   PYTHON3_HARDCODE  literal `python3` — often a broken WindowsApps alias;
#                     prefer resolving python3->python, and PYTHONUTF8=1.
#   HEREDOC_BACKSLASH `\n`/`\t` inside a bash heredoc — mangled across the
#                     shell boundary; use a patch file or printf.
#   CMD_SPAWN         spawning a .cmd/.bat from Node — EINVAL (CVE-2024-27980)
#                     unless shelled; resolve the real binary first.
#   SET_E_HOOK        `set -e` in a hooks/ script — the marketplace forbids it
#                     (a non-zero probe would abort the hook).
#
# Usage: scan-cli-hygiene.sh [path ...] [--json]   (default path: .)
set -uo pipefail

json_out="false"
paths=()
for arg in "$@"; do
  case "$arg" in
    --json) json_out="true" ;;
    *) paths+=("$arg") ;;
  esac
done
(( ${#paths[@]} )) || paths=(".")

# Source files worth scanning; skip vendored/generated trees and this scanner.
_self="$(basename "${BASH_SOURCE[0]}")"
list_files() {
  local p
  for p in "${paths[@]}"; do
    if [[ -f "$p" ]]; then echo "$p"; continue; fi
    find "$p" -type f \
      \( -name '*.py' -o -name '*.sh' -o -name '*.js' -o -name '*.cjs' \
         -o -name '*.mjs' -o -name '*.ts' \) \
      -not -path '*/node_modules/*' -not -path '*/.git/*' \
      -not -path '*/.venv/*' -not -path '*/dist/*' -not -path '*/build/*' \
      -not -name "$_self" 2>/dev/null
  done | sort -u
}

findings=()      # each: "file\tline\tRULE\tmessage"
add() { findings+=("$1"$'\t'"$2"$'\t'"$3"$'\t'"$4"); }

scan_file() {
  local f="$1" ext="${1##*.}" lineno=0 line
  while IFS= read -r line || [[ -n "$line" ]]; do
    lineno=$((lineno + 1))

    # NON_ASCII_OUTPUT — a print/echo sink on a line containing a non-ASCII byte.
    # `[^<tab><space>-~]` under LC_ALL=C matches any byte outside printable
    # ASCII (a BRE class, so no `grep -P` — which some builds refuse in the C
    # locale). Em-dash / arrow / ✎ are multi-byte UTF-8, all high bytes.
    if LC_ALL=C grep -q '[^'$'\t'' -~]' <<<"$line"; then
      case "$line" in
        *print\(*|*typer.echo*|*click.echo*|*console.log*|*process.stdout*|*'echo '*|*printf*)
          add "$f" "$lineno" "NON_ASCII_OUTPUT" \
            "non-ASCII char in a stdout string — crashes cp1252 Windows consoles" ;;
      esac
    fi

    case "$ext" in
      py)
        [[ "$line" == *python3* ]] && add "$f" "$lineno" "PYTHON3_HARDCODE" \
          "literal 'python3' — may be a broken WindowsApps alias; resolve python3->python" ;;
      sh)
        # set -e in a hooks/ path (bare, or leading segment of set -euo... is fine).
        if [[ "$f" == */hooks/* ]] && [[ "$line" =~ ^[[:space:]]*set[[:space:]]+-e([[:space:]]|$) ]]; then
          add "$f" "$lineno" "SET_E_HOOK" "set -e in a hook script — a probe's non-zero exit aborts the hook"
        fi ;;
      js|cjs|mjs|ts)
        if [[ "$line" == *spawn* && ( "$line" == *.cmd* || "$line" == *.bat* ) ]]; then
          add "$f" "$lineno" "CMD_SPAWN" "spawning .cmd/.bat from Node — EINVAL (CVE-2024-27980) without a shell"
        fi ;;
    esac
  done < "$f"

  # HEREDOC_BACKSLASH — an escaped \n/\t inside a bash heredoc body. Emitted as
  # file<TAB>line by one awk pass; collected into the array below (process
  # substitution, NOT a pipe, so `add` runs in THIS shell and the array keeps).
  if [[ "$ext" == "sh" ]]; then
    while IFS= read -r hl; do
      [[ -n "$hl" ]] && add "$f" "$hl" "HEREDOC_BACKSLASH" \
        "escaped \\n/\\t inside a heredoc — mangled across the shell boundary"
    done < <(awk '
      /<<-?[[:space:]]*[A-Za-z_"'"'"']+/ { inhd=1 }
      inhd && /(\\n|\\t)/ { print NR }
      inhd && /^[A-Za-z_]+[[:space:]]*$/ { inhd=0 }
    ' "$f" 2>/dev/null)
  fi
}

while IFS= read -r f; do
  [[ -n "$f" ]] && scan_file "$f"
done < <(list_files)

if [[ "$json_out" == "true" ]]; then
  out=""
  for entry in ${findings[@]+"${findings[@]}"}; do
    IFS=$'\t' read -r ff fl fr fm <<<"$entry"
    esc() { local s="${1//\\/\\\\}"; printf '%s' "${s//\"/\\\"}"; }
    out+="${out:+,}{\"file\":\"$(esc "$ff")\",\"line\":$fl,\"rule\":\"$fr\",\"message\":\"$(esc "$fm")\"}"
  done
  echo "{\"findings\":[$out],\"count\":${#findings[@]}}"
  exit 0
fi

if (( ${#findings[@]} == 0 )); then
  echo "cli-hygiene: no hazards found"
  exit 0
fi
for entry in "${findings[@]}"; do
  IFS=$'\t' read -r ff fl fr fm <<<"$entry"
  printf '%s:%s: %s %s\n' "$ff" "$fl" "$fr" "$fm"
done
echo "cli-hygiene: ${#findings[@]} advisory finding(s)"
exit 0
