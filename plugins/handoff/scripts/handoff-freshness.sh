#!/usr/bin/env bash
# handoff-freshness.sh — compare a handoff note's recorded state (the flat
# frontmatter handoff-meta.sh writes) against ACTUAL repo/anvil state, and
# report staleness flags so /recall never presents a stale resume point as
# current.
#
# Verdict semantics: informational, never blocking — ALWAYS exits 0. A legacy
# note with no frontmatter yields "freshness unavailable" (never a crash, per
# backward compat with every pre-0.2.0 note).
#
# Usage: handoff-freshness.sh [project_dir] [--json]
#   default: one human line per flag (or "fresh"), prefixed "handoff:"
#   --json:  {"available":bool,"fresh":bool,"flags":[...],"age_days":N|null}
set -uo pipefail

project_dir="$PWD"
json_out="false"
for arg in "$@"; do
  case "$arg" in
    --json) json_out="true" ;;
    *) project_dir="$arg" ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

emit() { # available fresh flags... (flags as remaining args)
  local available="$1" fresh="$2" age="$3"
  shift 3
  if [[ "$json_out" == "true" ]]; then
    local flags_json="" f
    for f in "$@"; do
      flags_json+="${flags_json:+,}\"${f//\"/\\\"}\""
    done
    printf '{"available":%s,"fresh":%s,"flags":[%s],"age_days":%s}\n' \
      "$available" "$fresh" "$flags_json" "$age"
  else
    if [[ "$available" != "true" ]]; then
      echo "handoff: freshness unavailable ($*)"
    elif [[ "$fresh" == "true" ]]; then
      echo "handoff: note is fresh (matches current repo state)"
    else
      local f
      for f in "$@"; do echo "handoff: STALE - $f"; done
    fi
  fi
  exit 0
}

handoff_file="$(bash "$SCRIPT_DIR/handoff-path.sh" "$project_dir" 2>/dev/null || true)"
[[ -n "$handoff_file" && -f "$handoff_file" ]] || emit false false null "no handoff note saved"

# Frontmatter = the block between a leading '---' line and the next '---'.
first_line="$(head -n 1 "$handoff_file" 2>/dev/null || true)"
[[ "$first_line" == "---" ]] || emit false false null "legacy note (no recorded state)"
fm="$(awk 'NR==1{next} /^---$/{exit} {print}' "$handoff_file")"

fm_get() { printf '%s\n' "$fm" | grep -m1 "^$1: " | sed "s/^$1: //"; }

saved_at="$(fm_get saved_at || true)"
rec_branch="$(fm_get branch || true)"
rec_head="$(fm_get head || true)"
rec_dirty="$(fm_get dirty_files || true)"
rec_claims="$(fm_get anvil_claims || true)"

flags=()

# Age (best-effort; date -d is GNU/Git Bash; fall back silently elsewhere).
age_days="null"
if [[ -n "$saved_at" ]]; then
  saved_epoch="$(date -u -d "$saved_at" +%s 2>/dev/null || true)"
  if [[ -n "$saved_epoch" ]]; then
    age_days=$(( ( $(date -u +%s) - saved_epoch ) / 86400 ))
    max_age="${HANDOFF_MAX_AGE_DAYS:-14}"
    if (( age_days > max_age )); then
      flags+=("note is ${age_days} days old (>${max_age}; set HANDOFF_MAX_AGE_DAYS to tune)")
    fi
  fi
fi

if git -C "$project_dir" rev-parse --git-dir >/dev/null 2>&1; then
  cur_branch="$(git -C "$project_dir" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  cur_head="$(git -C "$project_dir" rev-parse HEAD 2>/dev/null || true)"
  if [[ -n "$rec_branch" && -n "$cur_branch" && "$rec_branch" != "$cur_branch" ]]; then
    flags+=("branch moved: note saved on '$rec_branch', now on '$cur_branch'")
  fi
  if [[ -n "$rec_head" && -n "$cur_head" && "$rec_head" != "$cur_head" ]]; then
    # Distinguish "history advanced past the note" from "diverged".
    if git -C "$project_dir" merge-base --is-ancestor "$rec_head" "$cur_head" 2>/dev/null; then
      flags+=("HEAD advanced since save (${rec_head:0:8}.. -> ${cur_head:0:8}); 'Recently shipped' may be incomplete")
    else
      flags+=("HEAD diverged from the saved commit (${rec_head:0:8} not an ancestor of ${cur_head:0:8})")
    fi
  fi
fi

# Anvil claims recorded at save: are they still the live picture?
if [[ -n "$rec_claims" ]] && command -v anvil >/dev/null 2>&1; then
  live="$(anvil status --json --cwd "$project_dir" 2>/dev/null || true)"
  if [[ -n "$live" ]]; then
    IFS=',' read -ra pairs <<<"$rec_claims"
    for pair in "${pairs[@]}"; do
      # Split on the LAST colon: anvil task ids are composite
      # (feature:Txxx, e.g. evidence-contracts:T007), so the id itself
      # contains ':' — only the trailing :phase is ours.
      task="${pair%:*}"
      [[ -n "$task" && "$task" != "?" ]] || continue
      if ! printf '%s' "$live" | grep -q "\"task_id\": *\"$task\"" \
         && ! printf '%s' "$live" | grep -q "\"task\": *\"$task\""; then
        flags+=("claim on $task recorded at save is no longer active (released/expired/applied)")
      fi
    done
  fi
fi

if (( ${#flags[@]} == 0 )); then
  emit true true "$age_days"
else
  emit true false "$age_days" "${flags[@]}"
fi
