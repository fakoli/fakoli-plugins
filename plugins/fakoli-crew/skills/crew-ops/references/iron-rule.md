# The Iron Rule

Read every file in scope before editing any of them.

## The Rule

Before writing a single character of change, open and read every file that the task touches. Not just the target file — every file in scope. Read related configs, adjacent modules, and the files that reference what you are about to change.

## Why This Exists

The number-one cause of bad changes is editing a file without seeing the surrounding context. Production incidents attributed to this failure look identical: a one-line "safe" fix that broke an invariant the editor never knew existed, because the invariant lived two files over. The Iron Rule closes that gap completely. There is no exception for "small" or "obvious" changes — the judgment that a change is obvious requires the context that reading provides.

## How to Comply

Before any edit, read every file the task names, then read the files those files reference (configs, imports, callers). If a file has been read earlier in the session but the session is long, re-read it — sessions drift. When in doubt, read more.

## How to Announce Compliance

At the start of a task, state which files are in scope and confirm each has been read:

```
Files in scope: foo.ts, bar.ts, config/settings.json
Read: foo.ts (lines 1-120), bar.ts (lines 1-88), config/settings.json (lines 1-34)
Proceeding with edits.
```

This announcement is not ceremony. It is a checkpoint that forces the reading to happen before the editing starts.

## What Violations Look Like

- "I'll just update the version field" — without reading the full manifest
- Reading only the function being changed, not its callers
- Assuming a config value from memory rather than from a fresh read
- Skipping a file because it "probably hasn't changed"

Each of these has caused a broken plugin, a broken test suite, or a broken deploy. The rule exists because judgment fails under time pressure; the rule does not.

---

Agents bound by this rule: smith, keeper, critic, herald, welder, guido. Scout and sentinel are exempt — scout is read-only by role; sentinel validates without modifying source files.
