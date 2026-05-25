# fakoli-crew tests

Test infrastructure for the fakoli-crew plugin: agents (incl. critics), the
`/crew` command, and the four bundled skills.

## Conventions

### Bash-only, no Python dependency
fakoli-crew is a pure-markdown plugin: agents, command, skills. It has no
Python module, no `pyproject.toml`, no compiled assets. To keep installs lean
(zero pip dependencies inherited from the test suite), **all fakoli-crew tests
are written as bash scripts**. This follows the precedent set by
`plugins/fakoli-state/tests/test_hooks.sh`.

If a future test genuinely needs Python (e.g., parsing a complex YAML graph),
shell out to `python3 -c '...'` inline — do NOT add fakoli-crew to any
`pyproject.toml`.

### Script layout
```
tests/
├── README.md                 # this file
├── test_critics.sh           # runner stub for the 5 critic agents
└── fixtures/
    └── audit-targets/        # known-bad fixtures fed to each critic
```

### Manual-verification model
Critic agents are dispatched by Claude Code via the `Agent` tool, which is a
runtime concept inside an active Claude Code session. **Bash cannot dispatch a
subagent.** Therefore:

- `test_critics.sh` is a *recipe printer*, not a dispatcher. Run it with
  `--list` to see each critic name, the fixture it consumes, the severity
  label its findings must include, and a pointer to the full manual recipe
  (`RECIPES.md`, populated by T7).
- Actual critic invocation happens inside a Claude Code session by following
  the recipe: open the fixture, invoke the critic, inspect the status file it
  writes, verify the expected severity token appears.

This split exists because dispatching agents from a shell context is
impossible — the SDK requires a parent Claude Code conversation.

### Fixture conventions
Each file under `fixtures/audit-targets/` is a deliberately broken plugin
artifact (bad frontmatter, hardcoded path, wildcard matcher, etc.) sized to
trigger exactly one critic's MUST-FIX condition. Keep fixtures minimal: one
file, one failure mode, one expected severity.

## Running

```bash
# List all critic recipes (no Claude Code session required):
bash plugins/fakoli-crew/tests/test_critics.sh --list

# Show help:
bash plugins/fakoli-crew/tests/test_critics.sh --help
```

## CI

The bash runner with `--list` is safe to add to CI as a smoke check that the
recipe table stays in sync with the critic roster. The actual critic
invocations require a Claude Code session and are run manually per
`RECIPES.md`.
