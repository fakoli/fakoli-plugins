# cli-to-plugin

Turn any CLI with `--help` support into a Claude Code plugin in one command — one skill per
command group, plus user-curated workflow meta-skills.

---

## Quick start

```
/cli-to-plugin gh
```

Claude walks `gh --help`, discovers 12+ command groups, asks which ones to include, then
proposes workflow meta-skills (e.g., "review and merge PRs", "cut a release"). You pick.
The output is a standalone plugin — no runtime dependency on `cli-to-plugin` itself.

Generated file tree for `gh`:

```
gh/
├── .claude-plugin/plugin.json
├── skills/
│   ├── gh-pr/SKILL.md           # per-group: lists, creates, reviews, merges PRs
│   ├── gh-issue/SKILL.md
│   ├── gh-repo/SKILL.md
│   ├── gh-workflow/SKILL.md
│   ├── ...
│   ├── gh-review-and-merge/SKILL.md   # meta-skill: multi-step workflow
│   └── gh-cut-a-release/SKILL.md
└── README.md
```

Install the generated plugin:

```
/plugin install ./gh
```

---

## Prerequisites

- **uv** — Python script runner. Install:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **Target CLI** — the binary must be on your PATH (e.g., `gh`, `kubectl`, `docker`). Or
  pass `--from-tree` to skip live discovery entirely.
- **jq** — used by the marketplace validation scripts.
  ```bash
  brew install jq   # macOS
  apt-get install jq  # Linux
  ```

---

## How it works

1. **Preflight** — verifies `uv` and the target CLI are on PATH.
2. **Discovery** — runs `discover.py` via `uv`, which walks `<cli> --help` recursively and
   produces a structured JSON tree of groups, commands, and flags.
3. **Scope confirmation** — shows you the discovered groups; you pick which ones to include.
4. **Per-group skills** — Claude synthesizes a `SKILL.md` for each selected group. Each
   skill teaches Claude when and how to invoke that command group via Bash.
5. **Meta-skill proposals** — Claude reads the full help tree and proposes 5–10 workflow
   skills (multi-step sequences). You pick from the list (or type custom names).
6. **Write + validate** — all files are written atomically, then the marketplace validators
   run on the output. Errors halt; warnings appear in the summary.

---

## Flags

| Flag | Default | Description |
|---|---|---|
| `<cli-name>` | required | The binary to introspect (e.g., `gh`, `kubectl`) |
| `--out <path>` | `./plugins/<cli-name>` | Destination directory for the generated plugin |
| `--override <path>` | none | YAML file to skip groups, override descriptions, or pre-specify meta-skills |
| `--from-tree <path>` | none | Load a pre-captured help-tree JSON; skips live discovery |
| `--no-meta-skills` | off | Skip meta-skill proposal and generation entirely |
| `--regen` | off | When `--out` already exists, go straight to diff-and-merge without prompting |
| `--max-depth <n>` | 3 | Maximum recursion depth when walking subcommand help trees |
| `--max-commands <n>` | 500 | Halt discovery with a warning if command count exceeds this |

---

## Overrides

Create an `overrides.yaml` next to your invocation to customize generation without editing
generated files. The override file is re-read on every `--regen` run, so keep your
customizations here rather than hand-editing the output.

```yaml
plugin:
  name: gh
  author: {name: "Your Name"}

groups:
  - name: alias
    skip: true                        # no skill generated for this group

  - name: pr
    description: "Use when working with GitHub pull requests — listing, reviewing, merging."
    extra_guidance: |                 # appended to the generated skill body
      Default to --state open unless the user specifies otherwise.
      Prefer `gh pr view --web` when the user asks to "open" a PR.

meta_skills:
  # Providing this list skips the LLM proposal step entirely
  - name: gh-cut-a-release
    description: "Use when the user wants to tag and publish a new release."
    steps:
      - "gh release list"
      - "gh workflow run release.yml --ref main"
      - "gh release create v$VERSION --generate-notes"
```

All keys are optional. With no override file, Claude infers everything from the help tree.

Override behaviors:

| Key | Effect |
|---|---|
| `groups[].skip: true` | Removes the group from the tree before any skill is generated |
| `groups[].description` | Replaces the LLM-written trigger description verbatim |
| `groups[].extra_guidance` | Appended to the skill body as a `## Notes` section |
| `meta_skills` | Bypasses the LLM proposal step; uses your list as the proposal |

---

## Limitations

- **Skills only.** Generates `SKILL.md` files. Does not generate slash commands or agents.
- **No auto-update.** When the CLI version bumps, re-run with `--regen` manually.
- **Requires `--help` support.** Assumes a POSIX-ish CLI that emits structured help on
  `--help`. CLIs with non-standard or empty help output will warn or halt.
- **Meta-skill selection is interactive.** The multi-select picker requires a live Claude
  Code session. Use `--no-meta-skills` for headless / CI runs.
- **No marketplace publishing.** Generated plugins must be committed and submitted via PR
  manually — `cli-to-plugin` does not push or open PRs on your behalf.
- **Single-language CLIs only.** Does not handle CLIs whose subcommands shell out to
  separate binaries with different help formats (e.g., mixed Go + Python subcommands).

---

## See also

- **Spec:** [`docs/specs/2026-05-24-cli-to-plugin.md`](../../docs/specs/2026-05-24-cli-to-plugin.md) — full design, data model, error handling, and acceptance criteria
- **Playbook:** [`commands/cli-to-plugin.md`](commands/cli-to-plugin.md) — the step-by-step instructions Claude follows, including all flag definitions

---

## Author

Sekou Doumbouya — MIT License
