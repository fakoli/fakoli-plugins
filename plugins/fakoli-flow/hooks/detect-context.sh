#!/usr/bin/env bash

DETECTED_LANG="unknown"
[ -f "Cargo.toml" ] && DETECTED_LANG="Rust"
[ -f "pyproject.toml" ] && DETECTED_LANG="Python"
[ -f "setup.py" ] && DETECTED_LANG="Python"
[ -f "package.json" ] && DETECTED_LANG="TypeScript"
[ -f "tsconfig.json" ] && DETECTED_LANG="TypeScript"

CREW_STATUS="not installed"

if command -v claude >/dev/null 2>&1; then
  if claude plugin list 2>/dev/null | grep -q "fakoli-crew"; then
    CREW_VERSION=$(grep '"version"' ~/.claude/plugins/cache/fakoli-plugins/fakoli-crew/*/.claude-plugin/plugin.json 2>/dev/null | head -1 | grep -o '"[0-9][0-9.]*"' | tr -d '"')
    if [ -n "$CREW_VERSION" ]; then
      CREW_STATUS="$CREW_VERSION"
    else
      CREW_STATUS="installed"
    fi
  fi
fi

echo "[fakoli-flow] Language: $DETECTED_LANG | Crew: fakoli-crew $CREW_STATUS | Skills: brainstorm, plan, execute, verify, finish, quick"
