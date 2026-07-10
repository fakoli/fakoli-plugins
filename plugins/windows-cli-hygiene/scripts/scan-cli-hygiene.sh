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
    if [[ -f "$p" ]]; then
      # Explicit file arg: still skip the scanner itself (self-exclusion must
      # hold whether reached by walk or by a gate-router {files} list).
      [[ "$(basename "$p")" == "$_self" ]] || echo "$p"
      continue
    fi
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

# ERE for a heredoc opener; captures the delimiter word (quotes optional,
# `<<-` tab-strip variant allowed). In a var to keep the char class readable.
_hd_open='<<-?[[:space:]]*["'"'"']?([A-Za-z_][A-Za-z0-9_]*)'

scan_file() {
  local f="$1" ext="${1##*.}" lineno=0 line
  local in_hd="" delim="" stripped
  while IFS= read -r line || [[ -n "$line" ]]; do
    lineno=$((lineno + 1))
    line="${line%$'\r'}"   # strip a trailing CR so a CRLF checkout doesn't
                            # read as a non-ASCII byte (0x0D) or a mismatched
                            # heredoc delimiter.

    # --- inside a heredoc body: only HEREDOC_BACKSLASH applies -----------
    if [[ -n "$in_hd" && "$ext" == "sh" ]]; then
      stripped="${line#"${line%%[!$'\t']*}"}"   # drop leading tabs (<<- closer)
      if [[ "$stripped" == "$delim" ]]; then
        in_hd=""; delim=""
      elif [[ "$line" == *'\n'* || "$line" == *'\t'* ]]; then
        add "$f" "$lineno" "HEREDOC_BACKSLASH" \
          "escaped \\n/\\t inside a heredoc — mangled across the shell boundary"
      fi
      continue
    fi

    # --- heredoc opener (start tracking; the opener line itself is code) -
    if [[ "$ext" == "sh" && "$line" =~ $_hd_open ]]; then
      in_hd=1; delim="${BASH_REMATCH[1]}"
    fi

    # NON_ASCII_OUTPUT — a print/echo sink on a line with a non-ASCII byte.
    # `[^<tab><space>-~]` under LC_ALL=C matches any byte outside printable
    # ASCII (BRE class, so no `grep -P` — some builds refuse it in C locale).
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
        if [[ "$f" == */hooks/* ]] && [[ "$line" =~ ^[[:space:]]*set[[:space:]]+-e([[:space:]]|$) ]]; then
          add "$f" "$lineno" "SET_E_HOOK" "set -e in a hook script — a probe's non-zero exit aborts the hook"
        fi ;;
      js|cjs|mjs|ts)
        if [[ "$line" == *spawn* && ( "$line" == *.cmd* || "$line" == *.bat* ) ]]; then
          add "$f" "$lineno" "CMD_SPAWN" "spawning .cmd/.bat from Node — EINVAL (CVE-2024-27980) without a shell"
        fi ;;
    esac
  done < "$f"
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
