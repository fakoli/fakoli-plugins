#!/usr/bin/env bash

DETECTED_LANG="unknown"
[ -f "Cargo.toml" ] && DETECTED_LANG="Rust"
[ -f "pyproject.toml" ] && DETECTED_LANG="Python"
[ -f "setup.py" ] && DETECTED_LANG="Python"
[ -f "package.json" ] && DETECTED_LANG="TypeScript"
[ -f "tsconfig.json" ] && DETECTED_LANG="TypeScript"

CREW_STATUS="not installed"

if command -v claude >/dev/null 2>&1; then
  CREW_LIST=$(claude plugin list 2>/dev/null)
  if [ -n "$CREW_LIST" ] && grep -q "fakoli-crew" <<<"$CREW_LIST"; then
    # Fallback chain for version detection — never depend on one cache layout:
    # 1. Version printed on the plugin-list line itself (e.g. "fakoli-crew@2.2.0")
    CREW_VERSION=$(grep "fakoli-crew" <<<"$CREW_LIST" | head -1 | grep -o '[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*' | head -1)
    # 2. Any plugin cache or marketplace clone location (marketplace name not assumed)
    if [ -z "$CREW_VERSION" ]; then
      CREW_VERSION=$(grep -h '"version"' \
        "$HOME"/.claude/plugins/cache/*/fakoli-crew/*/.claude-plugin/plugin.json \
        "$HOME"/.claude/plugins/marketplaces/*/plugins/fakoli-crew/.claude-plugin/plugin.json \
        2>/dev/null | head -1 | grep -o '[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*' | head -1)
    fi
    if [ -n "$CREW_VERSION" ]; then
      CREW_STATUS="$CREW_VERSION"
    else
      CREW_STATUS="installed"
    fi
  fi
fi

echo "[fakoli-flow] Language: $DETECTED_LANG | Crew: fakoli-crew $CREW_STATUS | Skills: brainstorm, plan, execute, verify, finish, quick"
