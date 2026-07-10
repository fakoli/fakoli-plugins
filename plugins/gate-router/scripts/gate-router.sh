#!/usr/bin/env bash
# gate-router.sh — map CHANGED file paths to the verify commands this repo
# requires before those changes ship (the retro corpus's changed-path-gate-
# router: "docs changed -> docs strict build", "CLI changed -> encoding smoke
# test" — deterministic local gates instead of session memory).
#
# Rules live per-project in .claude/gate-router.local.md (the marketplace's
# plugin-settings pattern), one rule per line inside the frontmatter:
#
#   ---
#   rules:
#     - docs/** => mkdocs build --strict
#     - "**/*.sh" => bash -n {files}
#     - bin/src/** => cd bin && uv run pytest -q
#   ---
#
# Left of `=>` is a glob matched against each changed path (bash extended
# patterns: `**` handled as "any path prefix"); right is the command. `{files}`
# in a command expands to the space-separated matched files. Duplicate
# commands (matched via several rules/files) run once.
#
# Usage: gate-router.sh [project_dir] [--base <ref>] [--list|--run] [--json]
#   --base   diff base (default: origin/main if it exists, else HEAD)
#   --list   (default) print the required commands, one per line
#   --run    execute them in order, stop on first failure (exit = that rc)
#   --json   with --list: {"changed":N,"gates":[{"command":...,"files":[...]}]}
#
# Exit codes: 0 ok / nothing required; 2 config missing or unparseable;
# with --run: the first failing gate's exit code.
set -uo pipefail

project_dir="$PWD"
base=""
mode="list"
json_out="false"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --base) base="$2"; shift 2 ;;
    --list) mode="list"; shift ;;
    --run)  mode="run"; shift ;;
    --json) json_out="true"; shift ;;
    *) project_dir="$1"; shift ;;
  esac
done

cfg="$project_dir/.claude/gate-router.local.md"
if [[ ! -f "$cfg" ]]; then
  echo "gate-router: no config at .claude/gate-router.local.md (nothing to enforce)" >&2
  exit 0
fi

# Rules = frontmatter lines shaped `- <glob> => <command>` (quotes optional).
rules="$(awk 'NR==1 && $0!="---"{exit} NR>1 && $0=="---"{exit} NR>1{print}' "$cfg" \
  | sed -n 's/^[[:space:]]*-[[:space:]]*//p')"
if [[ -z "$rules" ]]; then
  echo "gate-router: config has no rules (frontmatter '- glob => command' lines)" >&2
  exit 2
fi

if ! git -C "$project_dir" rev-parse --git-dir >/dev/null 2>&1; then
  echo "gate-router: not a git repo" >&2
  exit 0
fi
if [[ -z "$base" ]]; then
  if git -C "$project_dir" rev-parse --verify origin/main >/dev/null 2>&1; then
    base="origin/main"
  else
    base="HEAD"
  fi
fi

# Changed = committed diff vs base + staged + unstaged + UNTRACKED (a brand-
# new file is the most common "about to ship" change and appears in no
# `git diff`). Deduped, forward slashes.
changed="$( (git -C "$project_dir" diff --name-only "$base" 2>/dev/null;
             git -C "$project_dir" diff --name-only --cached 2>/dev/null;
             git -C "$project_dir" diff --name-only 2>/dev/null;
             git -C "$project_dir" ls-files --others --exclude-standard 2>/dev/null) \
            | sort -u | grep -v '^$' \
            | grep -vx '.claude/gate-router.local.md' || true)"
# (the config itself is excluded: it is a local-only settings file that would
# otherwise read as "changed" forever and defeat the clean-tree no-op)
if [[ -z "$changed" ]]; then
  [[ "$json_out" == "true" ]] && echo '{"changed":0,"gates":[]}' || \
    echo "gate-router: no changed files vs $base"
  exit 0
fi

# Glob match: translate `**`-globs into bash case patterns. `**` -> `*`
# (case patterns already cross `/`); a leading `**/` also matches zero dirs.
matches_glob() { # path glob -> 0/1
  local path="$1" glob="$2" pat alt
  pat="${glob//\*\*/\*}"
  case "$path" in $pat) return 0 ;; esac
  if [[ "$glob" == "**/"* ]]; then
    alt="${glob#**/}"; alt="${alt//\*\*/\*}"
    case "$path" in $alt) return 0 ;; esac
  fi
  return 1
}

# Collect per-command matched files, preserving rule order.
cmds=()
declare -A cmd_files
while IFS= read -r rule; do
  glob="${rule%%=>*}"; glob="${glob%"${glob##*[![:space:]]}"}"
  # Quotes wrap the GLOB (YAML-style: - "**/*.sh" => cmd) — strip them here,
  # after the => split, so a closing quote mid-line is not left on the glob.
  glob="${glob#\"}"; glob="${glob%\"}"
  cmd="${rule#*=>}"; cmd="${cmd#"${cmd%%[![:space:]]*}"}"
  [[ -n "$glob" && -n "$cmd" && "$rule" == *"=>"* ]] || continue
  hits=""
  while IFS= read -r f; do
    matches_glob "$f" "$glob" && hits+="${hits:+ }$f"
  done <<<"$changed"
  [[ -n "$hits" ]] || continue
  if [[ -z "${cmd_files[$cmd]+x}" ]]; then
    cmds+=("$cmd")
    cmd_files[$cmd]="$hits"
  else
    cmd_files[$cmd]+=" $hits"
  fi
done <<<"$rules"

if (( ${#cmds[@]} == 0 )); then
  [[ "$json_out" == "true" ]] && echo "{\"changed\":$(wc -l <<<"$changed"),\"gates\":[]}" || \
    echo "gate-router: changed files match no gates"
  exit 0
fi

if [[ "$json_out" == "true" ]]; then
  out=""
  for cmd in "${cmds[@]}"; do
    files_json=""
    for f in ${cmd_files[$cmd]}; do files_json+="${files_json:+,}\"$f\""; done
    esc_cmd="${cmd//\\/\\\\}"; esc_cmd="${esc_cmd//\"/\\\"}"
    out+="${out:+,}{\"command\":\"$esc_cmd\",\"files\":[$files_json]}"
  done
  echo "{\"changed\":$(wc -l <<<"$changed"),\"gates\":[$out]}"
  exit 0
fi

rc=0
for cmd in "${cmds[@]}"; do
  final="${cmd//\{files\}/${cmd_files[$cmd]}}"
  if [[ "$mode" == "run" ]]; then
    echo "gate-router: RUN $final"
    ( cd "$project_dir" && bash -c "$final" )
    rc=$?
    if (( rc != 0 )); then
      echo "gate-router: GATE FAILED ($rc): $final" >&2
      exit $rc
    fi
  else
    echo "$final"
  fi
done
exit $rc
