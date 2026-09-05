#!/usr/bin/env bash
# Explicit offline suites: do not silently skip pytest tests via unittest discovery.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export TERM=dumb
unset FORCE_COLOR

run() { printf '\n[test] %s\n' "$1"; shift; "$@"; }

run 'marketplace operations and frontmatter' uv run --no-project --with PyYAML --with jsonschema python -m unittest discover -s tests -p 'test_*.py' -q
run 'release helper shell guards' bash tests/test-bump-plugin.sh
run 'plugin creator' uv run --no-project --with PyYAML python -m unittest discover -s tools/plugin-creator/tests -q
run 'Excalidraw conversion' node --test plugins/excalidraw-diagram/tests/convert.test.js
run 'Nano Banana CLI' uv run --project plugins/nano-banana-pro --locked python -m unittest discover -s plugins/nano-banana-pro/tests -q
run 'Fakoli State offline providers and state' uv run --project plugins/fakoli-state/bin --locked --extra all-providers pytest -c plugins/fakoli-state/bin/pyproject.toml plugins/fakoli-state/tests -q
run 'Fakoli State hooks' bash plugins/fakoli-state/tests/test_hooks.sh
run 'Fakoli Style ledger' uv run --no-project --with pytest --with jsonschema pytest plugins/fakoli-style/tests -q
run 'Fakoli Style projection' uv run --script plugins/fakoli-style/scripts/validate.py
run 'CLI generator with coverage' uv run --no-project --with pytest --with pytest-cov --with PyYAML pytest plugins/cli-to-plugin/tests --cov=plugins/cli-to-plugin/scripts --cov-fail-under=90 -q
run 'Systems Thinking offline contracts' bash -c 'cd plugins/systems-thinking && uv run --locked pytest tests -q'
run 'Ship task failure paths' python3 -m unittest discover -s plugins/ship-task/tests -p 'test_*.py' -q
run 'Ship task worktrees' bash plugins/ship-task/tests/test-ship-worktree.sh
run 'Ship loop packet contracts' bash plugins/ship-loop/tests/test-dispatch-packet-sections.sh
run 'Safe Fetch' uv run --project plugins/safe-fetch --extra dev pytest -c plugins/safe-fetch/pyproject.toml plugins/safe-fetch/tests -q
run 'Fleet Exec' uv run --project plugins/fleet-exec --extra dev pytest -c plugins/fleet-exec/pyproject.toml plugins/fleet-exec/tests -q
run 'Fakoli Speak' uv run --project plugins/fakoli-speak --extra dev pytest -c plugins/fakoli-speak/pyproject.toml plugins/fakoli-speak/tests -q
run 'Anvil Pulse dashboard' bash plugins/anvil-pulse/tests/test-server.sh
run 'Anvil Pulse lifecycle' python3 -m unittest discover -s plugins/anvil-pulse/tests -p 'test_*.py' -q
run 'Google Workspace common contracts' uv run --no-project --with PyYAML python -m unittest discover -s plugins/gws/tests -p 'test_*.py' -q
run 'Google Workspace structure' bash plugins/gws/scripts/test-plugin.sh
run 'NotebookLM installed launcher' python3 -m unittest discover -s plugins/notebooklm-enhanced/tests -p 'test_*.py' -q
run 'Handoff paths' bash plugins/handoff/tests/test-handoff-path.sh
run 'Handoff freshness' bash plugins/handoff/tests/test-handoff-freshness.sh
run 'Session retrospectives' uv run --no-project --with pytest pytest plugins/session-retro/tests -q
run 'Session evals' uv run --no-project --with pytest pytest plugins/session-evals/tests -q
run 'continuity and utility regression cases' uv run --no-project --with pytest --with PyYAML pytest plugins/handoff/tests plugins/quick-notes/tests plugins/skill-spec-lint/tests plugins/gate-router/tests plugins/windows-cli-hygiene/tests -q
run 'Quick Notes operations' python3 plugins/quick-notes/scripts/test_notes.py
run 'Skill specification lint' uv run --no-project --with PyYAML python plugins/skill-spec-lint/tests/test_skill_spec_lint.py
run 'Gate Router' bash plugins/gate-router/tests/test-gate-router.sh
run 'Windows CLI hygiene' bash plugins/windows-cli-hygiene/tests/test-scan-cli-hygiene.sh
run 'Archived sidecar fixtures' python3 -m unittest discover -s archive/k8s-sidecar-testing/tests -q
run 'Archived Rust rendered templates' env NETWORK_TEMPLATE_ALLOW_FETCH=1 python3 -m unittest discover -s archive/rust-network-module/tests -q
printf '\n[test] All offline suites passed. Authenticated service calls and live model evals were not run.\n'
