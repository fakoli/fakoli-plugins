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
# Left of `=>` is a glob matched against each changed path (segment-aware:
# `**` crosses directories, a single `*` stays within one path segment);
# right is the command. `{files}` passes the matched files to the command as
# separate ARGV (injection-safe — never interpolated into the shell).
# Duplicate commands (matched via several rules/files) run once, in rule order.
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

# Resolve the repo root and run every changed-file git command FROM it, so all
# paths are uniformly repo-root-relative. (git diff is root-relative but
# ls-files is cwd-relative — running both from the root removes that skew, and
# also makes globs like `docs/**` mean the same thing from any subdirectory.)
# `--show-prefix` gives the repo-relative subdir in git's own path form, so the
# config's root-relative path is immune to the MSYS-vs-native mismatch a
# show-toplevel string-strip would hit on Windows.
_git_root="$(git -C "$project_dir" rev-parse --show-toplevel 2>/dev/null || echo "$project_dir")"
_prefix="$(git -C "$project_dir" rev-parse --show-prefix 2>/dev/null || echo "")"
cfg_rel="${_prefix}.claude/gate-router.local.md"

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
changed="$( (git -C "$_git_root" diff --name-only "$base" 2>/dev/null;
             git -C "$_git_root" diff --name-only --cached 2>/dev/null;
             git -C "$_git_root" diff --name-only 2>/dev/null;
             git -C "$_git_root" ls-files --others --exclude-standard 2>/dev/null) \
            | sort -u | grep -v '^$' \
            | grep -Fvx "$cfg_rel" || true)"
# (the config itself is excluded: it is a local-only settings file that would
# otherwise read as "changed" forever and defeat the clean-tree no-op)
if [[ -z "$changed" ]]; then
  [[ "$json_out" == "true" ]] && echo '{"changed":0,"gates":[]}' || \
    echo "gate-router: no changed files vs $base"
  exit 0
fi

# Glob -> anchored ERE, matched with `[[ =~ ]]` (works on bash >= 3.2, so no
# bash-4-only features anywhere in this script). Segment-aware, unlike a bare
# `case`: a single `*` matches WITHIN one path segment (never crosses `/`),
# `**` crosses segments, `**/` also matches zero leading segments, `?` is one
# non-slash char. Character classes are NOT supported (`[` is literal) — keep
# path globs to `*`/`**`/`?`. This closes the over-match where `src/*.py`
# used to fire on `src/a/b/deep.py`.
glob_to_regex() {
  local glob="$1" re="" n=${#glob} i=0 c
  while (( i < n )); do
    c="${glob:i:1}"
    if [[ "$c" == "*" ]]; then
      if [[ "${glob:i:3}" == "**/" ]]; then re+='(.*/)?'; i=$((i+3)); continue; fi
      if [[ "${glob:i:2}" == "**" ]];  then re+='.*';      i=$((i+2)); continue; fi
      re+='[^/]*'; i=$((i+1)); continue
    fi
    case "$c" in
      '?') re+='[^/]' ;;
      .|+|\(|\)|\||\^|\$|\{|\}|\[|\]|\\) re+="\\$c" ;;
      *) re+="$c" ;;
    esac
    i=$((i+1))
  done
  printf '%s' "$re"
}
matches_glob() { # path glob -> 0/1
  local re; re="$(glob_to_regex "$2")"
  [[ "$1" =~ ^${re}$ ]]
}

# Per-command matched files, deduped, RULE ORDER — parallel indexed arrays
# (no associative array, so bash 3.2 / macOS is not a hard break). Each
# ucmd_files entry is a newline-joined file list; NL is a safe separator
# because git emits path names one-per-line (quoting NL-in-name paths).
ucmds=()
ucmd_files=()
cmd_index() { # echo index of "$1" in ucmds, or -1
  local i=0 c
  (( ${#ucmds[@]} == 0 )) && { echo -1; return; }
  for c in "${ucmds[@]}"; do
    [[ "$c" == "$1" ]] && { echo "$i"; return; }
    i=$((i+1))
  done
  echo -1
}

while IFS= read -r rule; do
  [[ "$rule" == *"=>"* ]] || continue
  glob="${rule%%=>*}"; glob="${glob%"${glob##*[![:space:]]}"}"
  # A quoted glob (YAML style: - "**/*.sh" => cmd): strip one wrapping quote
  # pair, after the => split so a stray quote isn't left on the glob.
  glob="${glob#\"}"; glob="${glob%\"}"
  cmd="${rule#*=>}"; cmd="${cmd#"${cmd%%[![:space:]]*}"}"
  [[ -n "$glob" && -n "$cmd" ]] || continue
  hits=""
  while IFS= read -r f; do
    [[ -n "$f" ]] && matches_glob "$f" "$glob" && hits+="${hits:+$'\n'}$f"
  done <<<"$changed"
  [[ -n "$hits" ]] || continue
  idx="$(cmd_index "$cmd")"
  if [[ "$idx" == "-1" ]]; then
    ucmds+=("$cmd")
    ucmd_files+=("$hits")
  else
    ucmd_files[$idx]="${ucmd_files[$idx]}"$'\n'"$hits"
  fi
done <<<"$rules"

if (( ${#ucmds[@]} == 0 )); then
  [[ "$json_out" == "true" ]] && echo "{\"changed\":$(wc -l <<<"$changed"),\"gates\":[]}" || \
    echo "gate-router: changed files match no gates"
  exit 0
fi

json_escape() { local s="${1//\\/\\\\}"; printf '%s' "${s//\"/\\\"}"; }

if [[ "$json_out" == "true" ]]; then
  out=""
  for i in "${!ucmds[@]}"; do
    files_json=""
    while IFS= read -r f; do
      [[ -n "$f" ]] || continue
      files_json+="${files_json:+,}\"$(json_escape "$f")\""
    done <<<"${ucmd_files[$i]}"
    out+="${out:+,}{\"command\":\"$(json_escape "${ucmds[$i]}")\",\"files\":[$files_json]}"
  done
  echo "{\"changed\":$(wc -l <<<"$changed"),\"gates\":[$out]}"
  exit 0
fi

rc=0
for i in "${!ucmds[@]}"; do
  cmd="${ucmds[$i]}"
  # Read this command's files into a real array (quoted expansion → filenames
  # with spaces/metacharacters stay ONE argument each).
  files=()
  while IFS= read -r f; do [[ -n "$f" ]] && files+=("$f"); done <<<"${ucmd_files[$i]}"

  if [[ "$mode" == "run" ]]; then
    # SECURITY: never interpolate a filename into the shell string. `{files}`
    # is rewritten to "$@" and the matched files are passed as positional
    # ARGV to bash -c, so a changed file literally named `$(rm -rf ~)` is an
    # inert argument, not code. Commands without {files} still get the files
    # as extra args (harmless).
    template="${cmd//\{files\}/\"\$@\"}"
    printf 'gate-router: RUN %s\n' "$cmd"
    if (( ${#files[@]} )); then printf '  on: %s\n' "${files[*]}"; fi
    # Run from the repo root so root-relative {files} resolve correctly.
    ( cd "$_git_root" && bash -c "$template" gate-router "${files[@]}" )
    rc=$?
    if (( rc != 0 )); then
      echo "gate-router: GATE FAILED ($rc): $cmd" >&2
      exit $rc
    fi
  else
    # --list is copy-paste output: render {files} as shell-QUOTED names so a
    # human pasting the line is also injection-safe.
    if [[ "$cmd" == *"{files}"* ]]; then
      quoted=""
      for f in "${files[@]}"; do quoted+="${quoted:+ }$(printf '%q' "$f")"; done
      printf '%s\n' "${cmd//\{files\}/$quoted}"
    else
      printf '%s\n' "$cmd"
    fi
  fi
done
exit $rc
