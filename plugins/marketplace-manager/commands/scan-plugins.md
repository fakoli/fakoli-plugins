---
name: scan-plugins
description: Deep scan all plugins for path resolution issues and hook safety problems
---

# Plugin Deep Scanner

Run the deep scanner to check all plugins for path resolution issues and hook safety problems.

## Instructions

1. Run the scanner script:

```bash
./scripts/test-path-resolution.sh
```

2. Review the output for:
   - **ERRORS** — must be fixed before merging (broken paths, dangerous hook patterns)
   - **WARNINGS** — should be addressed (unnecessary manifest fields, missing timeouts, `set -e` usage)

3. To scan a specific plugin:

```bash
./scripts/test-path-resolution.sh plugins/<name>
```

4. Report the results to the user with a summary of any issues found and recommended fixes.

## What It Checks

**Path Resolution:**
- Component paths resolve correctly relative to `.claude-plugin/`
- Auto-discovered directories aren't redundantly declared in manifest
- `./` vs `../` path confusion detection
- `.mcp.json` JSON syntax validation

**Hook Safety:**
- Broad/missing matchers on high-frequency events
- `prompt`-type hooks on `UserPromptSubmit` (conversation hijack)
- `set -e` in hook scripts (breaks fallback patterns)
- `cat | grep` anti-patterns (ARG_MAX risk)
- Missing timeouts on command hooks
- Script existence verification
