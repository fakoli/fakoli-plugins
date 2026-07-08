#!/usr/bin/env bash
#
# bump-plugin.sh — bump one plugin's version in lockstep, with nothing missed.
#
# In this marketplace a plugin's version lives in its plugin.json, and
# generate-index.sh DERIVES the version in .claude-plugin/marketplace.json and
# registry/*.json from it. Bumping plugin.json by hand and forgetting to
# regenerate — or regenerating but staging only some of the outputs — leaves
# the three sources out of sync, which the registry-drift CI gate rejects.
#
# This does the whole thing from one command: bump plugin.json, regenerate the
# derived files, verify (drift + validate), and stage the COMPLETE set so a
# partial `git add` can't drift them again. Then you just commit.
#
# Harness-agnostic: bash + jq + python3 (all already required by this repo),
# so it runs the same under Claude, Codex, or a plain shell.
#
# Usage:
#   scripts/bump-plugin.sh <plugin> <major|minor|patch|X.Y.Z> [options]
#
# Options:
#   --dry-run    print the plan and exit; change nothing
#   --no-stage   apply + regenerate + verify but do not `git add` the result
#   -h, --help   this help
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

die()  { printf 'bump-plugin: %s\n' "$1" >&2; exit "${2:-1}"; }
say()  { printf '  bump: %s\n' "$*"; }

usage() { sed -n '2,30p' "$0" | grep -E '^#( |$)' | sed 's/^#\{0,1\} \{0,1\}//'; }

PLUGIN=""
SPEC=""
DRY_RUN=false
STAGE=true
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=true; shift ;;
    --no-stage) STAGE=false; shift ;;
    -h|--help) usage; exit 0 ;;
    -*) die "unknown option '$1'" ;;
    *)
      if [ -z "$PLUGIN" ]; then PLUGIN="$1"
      elif [ -z "$SPEC" ]; then SPEC="$1"
      else die "unexpected argument '$1'"; fi
      shift ;;
  esac
done

[ -n "$PLUGIN" ] && [ -n "$SPEC" ] || { usage; die "need <plugin> and <major|minor|patch|X.Y.Z>"; }
command -v jq >/dev/null 2>&1 || die "jq not found (brew install jq)"
command -v python3 >/dev/null 2>&1 || die "python3 not found"

MANIFEST="$ROOT_DIR/plugins/$PLUGIN/.claude-plugin/plugin.json"
[ -f "$MANIFEST" ] || die "no such plugin: plugins/$PLUGIN/.claude-plugin/plugin.json missing"

CUR="$(jq -r '.version // empty' "$MANIFEST")"
[ -n "$CUR" ] || die "plugins/$PLUGIN has no version in plugin.json"
[[ "$CUR" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "current version '$CUR' is not semver"

# --- compute the new version ---
if [[ "$SPEC" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  NEW="$SPEC"
else
  IFS=. read -r MA MI PA <<< "$CUR"
  case "$SPEC" in
    major) NEW="$((MA + 1)).0.0" ;;
    minor) NEW="${MA}.$((MI + 1)).0" ;;
    patch) NEW="${MA}.${MI}.$((PA + 1))" ;;
    *) die "invalid version spec '$SPEC' — use major|minor|patch|X.Y.Z" ;;
  esac
fi

if [ "$NEW" = "$CUR" ]; then
  say "$PLUGIN already at $CUR — nothing to do"
  exit 0
fi

echo "bump: $PLUGIN  $CUR -> $NEW$($DRY_RUN && echo '  [DRY RUN]')"

if $DRY_RUN; then
  cat <<PLAN
  would edit   plugins/$PLUGIN/.claude-plugin/plugin.json  (version -> $NEW)
  would run    scripts/generate-index.sh   (re-derives marketplace.json + registry/*)
  would verify scripts/check-registry-drift.sh + scripts/validate.sh plugins/$PLUGIN
  would stage  plugins/$PLUGIN .claude-plugin/marketplace.json registry/  $($STAGE || echo '(--no-stage: skipped)')
  reminder     add a plugins/$PLUGIN/CHANGELOG.md entry for $NEW before committing
PLAN
  exit 0
fi

# --- 1. bump plugin.json (surgical: only the version value, preserve formatting) ---
python3 - "$MANIFEST" "$CUR" "$NEW" <<'PY'
import re, sys
path, cur, new = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(path, encoding="utf-8").read()
pat = r'("version"\s*:\s*")' + re.escape(cur) + r'(")'
out, n = re.subn(pat, r"\g<1>" + new + r"\g<2>", text, count=1)
if n != 1:
    sys.exit(f"could not rewrite version in {path}")
open(path, "w", encoding="utf-8").write(out)
PY
[ $? -eq 0 ] || die "failed to edit plugin.json"
say "plugin.json -> $NEW"

# --- 2. regenerate the DERIVED files (marketplace.json versions + registry/*) ---
say "regenerating marketplace.json + registry ..."
"$SCRIPT_DIR/generate-index.sh" >/dev/null 2>&1 || die "generate-index.sh failed" 1

# --- 3. verify: no drift, plugin still valid ---
say "verifying (registry drift + validate) ..."
if ! "$SCRIPT_DIR/check-registry-drift.sh" >/dev/null 2>&1; then
  die "registry drift after regenerate — the sources disagree; inspect with scripts/check-registry-drift.sh" 2
fi
if ! "$SCRIPT_DIR/validate.sh" "plugins/$PLUGIN" >/dev/null 2>&1; then
  die "validate.sh failed for plugins/$PLUGIN — inspect with scripts/validate.sh plugins/$PLUGIN" 2
fi
say "verified: no drift, plugin valid"

# --- 4. stage the COMPLETE set so it can't drift via a partial add ---
STAGED_NOTE="(not staged — --no-stage)"
if $STAGE; then
  git -C "$ROOT_DIR" add \
    "plugins/$PLUGIN" ".claude-plugin/marketplace.json" "registry" >/dev/null 2>&1 \
    && STAGED_NOTE="staged: plugins/$PLUGIN .claude-plugin/marketplace.json registry/" \
    || STAGED_NOTE="WARNING: git add failed — stage the three sources manually"
fi

echo ""
echo "bump: $PLUGIN $CUR -> $NEW done."
say "$STAGED_NOTE"
say "next: add a plugins/$PLUGIN/CHANGELOG.md entry for $NEW, then commit."
