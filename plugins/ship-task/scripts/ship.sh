#!/usr/bin/env bash
#
# ship.sh — the mechanical tail of a one-PR-per-task loop, as a single command.
#
# Runs AFTER your review/verification passes: push the current branch, open a
# PR, wait for CI to reach a terminal state, merge (squash + delete branch),
# sync the base branch, and optionally run a post-merge command. Prints one
# compact summary line per stage instead of a screenful of git/gh output — the
# point is to keep the loop out of an agent's context window.
#
# It makes NO judgement calls: no code review, no "should this merge". You
# gate that before calling ship. If CI fails, ship stops and leaves the PR open.
#
set -uo pipefail

# --------------------------------------------------------------------------
# defaults
# --------------------------------------------------------------------------
TITLE=""
BODY=""
BODY_FILE=""
BASE=""
THEN=""
MERGE_METHOD="--squash"
DRAFT=false
NO_WAIT=false
ADMIN=false
UNSET_TOKEN=false
POLL_SECS=20
TIMEOUT_SECS=1800
DRY_RUN=false

usage() {
  cat <<'USAGE'
ship.sh — the mechanical tail of a one-PR-per-task loop, as a single command.

Runs AFTER your review/verification passes: push the current branch, open a
PR, wait for CI to reach a terminal state, merge (squash + delete branch),
sync the base branch, and optionally run a post-merge command. Makes no review
decisions; if CI fails it stops and leaves the PR open.

Usage: ship.sh [options] "PR title"

Options:
  --body TEXT          PR body (inline)
  --body-file FILE     PR body read from a file (use "-" for stdin)
  --base BRANCH        base branch (default: the repo's default branch)
  --then "CMD"         shell command to run after a successful merge
                       (e.g. --then "anvil apply T007 --approve --reviewer me")
  --draft              open the PR as a draft and stop (no CI wait, no merge)
  --no-wait            skip CI polling; merge as soon as the PR is mergeable
  --merge|--rebase|--squash   merge method (default: --squash)
  --admin              pass --admin to `gh pr merge` (bypass required checks
                       if you have the rights)
  --unset-token        run every `gh` call as `env -u GITHUB_TOKEN gh ...`
                       (workaround for an ambient PAT that lacks repo scope)
  --poll-secs N        CI poll interval in seconds (default: 20)
  --timeout-secs N     max seconds to wait for CI (default: 1800)
  --dry-run            print the plan and exit; touch nothing
  -h, --help           this help

Exit codes: 0 shipped (and --then, if any, succeeded) · 1 usage/preflight
error · 2 CI failed (PR left open) · 3 merge failed · 4 --then command failed.
USAGE
}

# --------------------------------------------------------------------------
# args
# --------------------------------------------------------------------------
while [ $# -gt 0 ]; do
  case "$1" in
    --body)         BODY="${2:-}"; shift 2 ;;
    --body-file)    BODY_FILE="${2:-}"; shift 2 ;;
    --base)         BASE="${2:-}"; shift 2 ;;
    --then)         THEN="${2:-}"; shift 2 ;;
    --draft)        DRAFT=true; shift ;;
    --no-wait)      NO_WAIT=true; shift ;;
    --squash)       MERGE_METHOD="--squash"; shift ;;
    --merge)        MERGE_METHOD="--merge"; shift ;;
    --rebase)       MERGE_METHOD="--rebase"; shift ;;
    --admin)        ADMIN=true; shift ;;
    --unset-token)  UNSET_TOKEN=true; shift ;;
    --poll-secs)    POLL_SECS="${2:-}"; shift 2 ;;
    --timeout-secs) TIMEOUT_SECS="${2:-}"; shift 2 ;;
    --dry-run)      DRY_RUN=true; shift ;;
    -h|--help)      usage; exit 0 ;;
    --) shift; break ;;
    -*) echo "ship: unknown option '$1'" >&2; exit 1 ;;
    *)  if [ -z "$TITLE" ]; then TITLE="$1"; else echo "ship: unexpected arg '$1'" >&2; exit 1; fi; shift ;;
  esac
done

say()  { printf '  ship: %s\n' "$*"; }
die()  { printf 'ship: %s\n' "$1" >&2; exit "${2:-1}"; }

# `gh` wrapper honoring --unset-token
_gh() {
  if $UNSET_TOKEN; then env -u GITHUB_TOKEN gh "$@"; else gh "$@"; fi
}

# `git` wrapper for NETWORK ops (push/pull/fetch) honoring --unset-token — in
# environments where an ambient GITHUB_TOKEN lacks repo scope, git's own
# credential helper must fall back to the keyring, which only happens when the
# variable is absent. Local git ops don't need this.
_git_net() {
  if $UNSET_TOKEN; then env -u GITHUB_TOKEN git "$@"; else git "$@"; fi
}

# --------------------------------------------------------------------------
# preflight
# --------------------------------------------------------------------------
[ -n "$TITLE" ] || { usage; die "a PR title is required" 1; }
command -v git >/dev/null 2>&1 || die "git not found" 1
command -v gh  >/dev/null 2>&1 || die "gh (GitHub CLI) not found — see https://cli.github.com" 1
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "not inside a git repository" 1

BRANCH="$(git branch --show-current)"
[ -n "$BRANCH" ] || die "detached HEAD — checkout a branch before shipping" 1

if [ -z "$BASE" ]; then
  BASE="$(_gh repo view --json defaultBranchRef -q .defaultBranchRef.name 2>/dev/null)"
  [ -n "$BASE" ] || BASE="main"
fi
[ "$BRANCH" != "$BASE" ] || die "refusing to ship: you are on the base branch '$BASE'. Branch first." 1

# body resolution
if [ -n "$BODY_FILE" ]; then
  if [ "$BODY_FILE" = "-" ]; then BODY="$(cat)"; else
    [ -f "$BODY_FILE" ] || die "body file not found: $BODY_FILE" 1
    BODY="$(cat "$BODY_FILE")"
  fi
fi

# uncommitted-work warning — ship pushes only what's committed
if ! git diff --quiet || ! git diff --cached --quiet; then
  say "WARNING: uncommitted changes present — they will NOT be in the PR. Commit first if you meant to include them."
fi

if $DRY_RUN; then
  cat <<PLAN
ship: DRY RUN — plan only
  branch      $BRANCH  ->  base $BASE
  title       $TITLE
  merge       ${MERGE_METHOD#--}$($ADMIN && echo " --admin")$($DRAFT && echo "  (DRAFT: open only)")
  ci wait     $($NO_WAIT && echo "no" || echo "yes (poll ${POLL_SECS}s, timeout ${TIMEOUT_SECS}s)")
  gh token    $($UNSET_TOKEN && echo "unset GITHUB_TOKEN" || echo "default")
  then        ${THEN:-<none>}
PLAN
  exit 0
fi

# --------------------------------------------------------------------------
# 1. push
# --------------------------------------------------------------------------
say "pushing $BRANCH ..."
push_err="$(_git_net push -u origin HEAD 2>&1 >/dev/null)" || die "git push failed: ${push_err:-see git output}" 1

# --------------------------------------------------------------------------
# 2. open PR (reuse an existing one for this branch if present)
# --------------------------------------------------------------------------
PR_NUM="$(_gh pr view "$BRANCH" --json number -q .number 2>/dev/null)"
if [ -z "$PR_NUM" ]; then
  args=(pr create --base "$BASE" --head "$BRANCH" --title "$TITLE")
  if [ -n "$BODY" ]; then args+=(--body "$BODY"); else args+=(--body ""); fi
  $DRAFT && args+=(--draft)
  PR_URL="$(_gh "${args[@]}" 2>&1 | tail -1)"
  case "$PR_URL" in
    http*) : ;;
    *) die "gh pr create failed: $PR_URL" 1 ;;
  esac
  PR_NUM="${PR_URL##*/}"
else
  PR_URL="$(_gh pr view "$PR_NUM" --json url -q .url 2>/dev/null)"
  say "reusing existing PR #$PR_NUM"
fi
say "PR #$PR_NUM · $PR_URL"

if $DRAFT; then
  say "draft opened — stopping before CI/merge as requested"
  printf 'ship: DRAFT #%s · %s\n' "$PR_NUM" "$PR_URL"
  exit 0
fi

# --------------------------------------------------------------------------
# 3. wait for CI to reach a terminal state
# --------------------------------------------------------------------------
CI="skipped"
if ! $NO_WAIT; then
  say "waiting for CI (poll ${POLL_SECS}s, timeout ${TIMEOUT_SECS}s) ..."
  waited=0
  failing=""
  while :; do
    # Structured status: one "<bucket>\t<name>" line per check. `bucket` is
    # gh's own classification (pass|fail|pending|skipping|cancel) — far more
    # robust than grepping display text, where a check literally NAMED
    # "test-failover" would otherwise read as a failure.
    rows="$(_gh pr checks "$PR_NUM" --json bucket,name -q '.[] | "\(.bucket)\t\(.name)"' 2>/dev/null)"
    if [ -z "$rows" ]; then
      # No checks configured on this repo/PR → nothing to gate on.
      CI="none"; break
    fi
    if printf '%s\n' "$rows" | grep -q '^pending'; then
      [ "$waited" -ge "$TIMEOUT_SECS" ] && { CI="timeout"; break; }
      sleep "$POLL_SECS"; waited=$((waited + POLL_SECS)); continue
    fi
    failing="$(printf '%s\n' "$rows" | grep -E '^(fail|cancel)')"
    if [ -n "$failing" ]; then CI="failed"; else CI="passed"; fi
    break
  done

  if [ "$CI" = "failed" ] || [ "$CI" = "timeout" ]; then
    say "CI $CI — leaving PR #$PR_NUM open, not merging"
    [ -n "$failing" ] && printf '%s\n' "$failing" | sed 's/^/    /'
    printf 'ship: CI %s · PR #%s left open · %s\n' "$CI" "$PR_NUM" "$PR_URL"
    exit 2
  fi
  say "CI $CI"
fi

# --------------------------------------------------------------------------
# 4. merge + delete branch
# --------------------------------------------------------------------------
say "merging (${MERGE_METHOD#--}) ..."
merge_args=(pr merge "$PR_NUM" "$MERGE_METHOD" --delete-branch)
$ADMIN && merge_args+=(--admin)
if ! _gh "${merge_args[@]}" >/dev/null 2>&1; then
  die "gh pr merge failed for #$PR_NUM (PR left open) — check required reviews/branch protection, or pass --admin" 3
fi
MERGE_SHA="$(_gh pr view "$PR_NUM" --json mergeCommit -q .mergeCommit.oid 2>/dev/null | cut -c1-9)"

# --------------------------------------------------------------------------
# 5. sync base
# --------------------------------------------------------------------------
say "syncing $BASE ..."
git checkout "$BASE" >/dev/null 2>&1 || die "merged, but 'git checkout $BASE' failed — sync manually" 3
_git_net pull --ff-only >/dev/null 2>&1 || say "WARNING: 'git pull' on $BASE did not fast-forward — reconcile manually"

# --------------------------------------------------------------------------
# 6. post-merge hook
# --------------------------------------------------------------------------
THEN_STATUS="—"
if [ -n "$THEN" ]; then
  say "running post-merge: $THEN"
  if eval "$THEN"; then THEN_STATUS="ok"; else
    THEN_STATUS="FAILED"
    printf 'ship: MERGED #%s (%s) but --then failed: %s\n' "$PR_NUM" "${MERGE_SHA:-?}" "$THEN"
    exit 4
  fi
fi

# --------------------------------------------------------------------------
# summary
# --------------------------------------------------------------------------
printf 'ship: PR #%s · CI %s · merged %s · then %s · %s\n' \
  "$PR_NUM" "$CI" "${MERGE_SHA:-?}" "$THEN_STATUS" "$PR_URL"
