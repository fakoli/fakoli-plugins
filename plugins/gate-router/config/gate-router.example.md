---
rules:
  # glob => command. `**` crosses directories; a single `*` stays within one
  # path segment; a leading `**/` also matches root-level files. `{files}`
  # passes the matched files as separate arguments (safe for spaces/metachars).
  - "**/*.sh" => bash -n {files}
  - docs/** => echo "TODO: docs strict build, e.g. mkdocs build --strict"
  # - src/** => echo "TODO: your test suite"
---
# gate-router rules for this project.
#
# Copy to .claude/gate-router.local.md and edit. Derive gates from your CI
# workflow steps, CLAUDE.md test instructions, and past incident classes.
# SECURITY: these commands run with your privileges on `--run` — treat this
# file like a Makefile. Gitignore .claude/gate-router.local.md unless you mean
# to share a reviewed gate policy with the team.
