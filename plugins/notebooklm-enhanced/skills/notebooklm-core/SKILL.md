---
name: notebooklm-core
description: Complete Google NotebookLM automation — create notebooks, add sources, generate podcasts/videos/quizzes/slides, chat with content, and download results. Activates on explicit /notebooklm-enhanced commands or intent like "create a podcast about X", "summarize these URLs", "generate a quiz"
---

# NotebookLM Automation

Complete programmatic access to Google NotebookLM — including capabilities not exposed in the web UI. Create notebooks, add sources (URLs, YouTube, PDFs, audio, video, images), chat with content, generate all artifact types (podcasts, videos, quizzes, flashcards, slide decks, infographics, reports, mind maps, data tables), and download results in multiple formats.

## CLI Prefix

**ALL commands** in this skill must be run with the following prefix:

```bash
uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm ...
```

Throughout this document, commands are shown with just `notebooklm` for brevity. Always prepend `uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts"` before every invocation.

## Prerequisites

**IMPORTANT:** Before using any command, verify authentication:

```bash
uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm auth check
uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm list
```

If commands fail with authentication errors, re-run login:

```bash
uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm login
```

### CI/CD, Multiple Accounts, and Parallel Agents

| Variable | Purpose |
|----------|---------|
| `NOTEBOOKLM_HOME` | Custom config directory (default: `~/.notebooklm`) |
| `NOTEBOOKLM_AUTH_JSON` | Inline auth JSON — no file writes needed |

**CI/CD setup:** Set `NOTEBOOKLM_AUTH_JSON` from a secret containing your `storage_state.json` contents.

**Multiple accounts:** Use different `NOTEBOOKLM_HOME` directories per account.

## When This Skill Activates

**Explicit triggers:** User says "/notebooklm-enhanced", "/notebooklm", "use notebooklm", or mentions the tool by name.

**Intent detection — activate when the user asks to:**
- "Create a podcast about [topic]"
- "Summarize these URLs/documents"
- "Generate a quiz from my research"
- "Turn this into an audio overview"
- "Create flashcards for studying"
- "Generate a video explainer"
- "Make an infographic"
- "Create a mind map of the concepts"
- "Download the quiz as markdown"
- "Add these sources to NotebookLM"

## Autonomy Rules

**Run automatically (no confirmation needed):**
- `notebooklm status` — check context
- `notebooklm auth check` — diagnose auth issues
- `notebooklm list` — list notebooks
- `notebooklm source list` — list sources
- `notebooklm artifact list` — list artifacts
- `notebooklm language list` — list supported languages
- `notebooklm language get` — get current language
- `notebooklm language set` — set language (global setting)
- `notebooklm artifact wait` — wait for artifact completion (in subagent context)
- `notebooklm source wait` — wait for source processing (in subagent context)
- `notebooklm research status` — check research status
- `notebooklm research wait` — wait for research (in subagent context)
- `notebooklm use <id>` — set context (single-agent only; use `-n` flag in parallel workflows)
- `notebooklm create` — create notebook
- `notebooklm ask "..."` — chat queries (without `--save-as-note`)
- `notebooklm history` — display conversation history (read-only)
- `notebooklm source add` — add sources

- `notebooklm notebook delete` — destructive
- `notebooklm delete` — destructive
- `notebooklm generate *` — long-running, may fail
- `notebooklm download *` — writes to filesystem
- `notebooklm artifact wait` — long-running (when in main conversation)
- `notebooklm source wait` — long-running (when in main conversation)
- `notebooklm research wait` — long-running (when in main conversation)
- `notebooklm ask "..." --save-as-note` — writes a note
- `notebooklm history --save` — writes a note

## Quick Reference

All commands below must be prefixed with `uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts"`.

| Task | Command |
|------|---------|
| Authenticate | `notebooklm login` |
| Diagnose auth issues | `notebooklm auth check` |
| Diagnose auth (full) | `notebooklm auth check --test` |
| List notebooks | `notebooklm list` |
| Create notebook | `notebooklm create "Title"` |
| Set context | `notebooklm use <notebook_id>` |
| Show context | `notebooklm status` |
| Add URL source | `notebooklm source add "https://..."` |
| Add file | `notebooklm source add ./file.pdf` |
| Add YouTube | `notebooklm source add "https://youtube.com/..."` |
| List sources | `notebooklm source list` |
| Delete source by ID | `notebooklm source delete <source_id>` |
| Delete source by exact title | `notebooklm source delete-by-title "Exact Title"` |
| Wait for source processing | `notebooklm source wait <source_id>` |
| Web research (fast) | `notebooklm source add-research "query"` |
| Web research (deep) | `notebooklm source add-research "query" --mode deep --no-wait` |
| Check research status | `notebooklm research status` |
| Wait for research | `notebooklm research wait --import-all` |
| Chat | `notebooklm ask "question"` |
| Chat (specific sources) | `notebooklm ask "question" -s src_id1 -s src_id2` |
| Chat (with references) | `notebooklm ask "question" --json` |
| Chat (save answer as note) | `notebooklm ask "question" --save-as-note` |
| Chat (save with title) | `notebooklm ask "question" --save-as-note --note-title "Title"` |
| Show conversation history | `notebooklm history` |
| Save all history as note | `notebooklm history --save` |
| Continue specific conversation | `notebooklm ask "question" -c <conversation_id>` |
| Save history with title | `notebooklm history --save --note-title "My Research"` |
| Get source fulltext | `notebooklm source fulltext <source_id>` |
| Get source guide | `notebooklm source guide <source_id>` |
| Generate podcast | `notebooklm generate audio "instructions"` |
| Generate podcast (JSON) | `notebooklm generate audio --json` |
| Generate podcast (specific sources) | `notebooklm generate audio -s src_id1 -s src_id2` |
| Generate video | `notebooklm generate video "instructions"` |
| Generate report | `notebooklm generate report --format briefing-doc` |
| Generate report (append instructions) | `notebooklm generate report --format study-guide --append "Target audience: beginners"` |
| Generate quiz | `notebooklm generate quiz` |
| Generate flashcards | `notebooklm generate flashcards` |
| Generate slide deck | `notebooklm generate slide-deck` |
| Generate infographic | `notebooklm generate infographic` |
| Generate mind map | `notebooklm generate mind-map` |
| Generate data table | `notebooklm generate data-table "description"` |
| Revise a slide | `notebooklm generate revise-slide "prompt" --artifact <id> --slide 0` |
| Check artifact status | `notebooklm artifact list` |
| Wait for completion | `notebooklm artifact wait <artifact_id>` |
| Download audio | `notebooklm download audio ./output.mp3` |
| Download video | `notebooklm download video ./output.mp4` |
| Download slide deck (PDF) | `notebooklm download slide-deck ./slides.pdf` |
| Download slide deck (PPTX) | `notebooklm download slide-deck ./slides.pptx --format pptx` |
| Download report | `notebooklm download report ./report.md` |
| Download mind map | `notebooklm download mind-map ./map.json` |
| Download data table | `notebooklm download data-table ./data.csv` |
| Download quiz | `notebooklm download quiz quiz.json` |
| Download quiz (markdown) | `notebooklm download quiz --format markdown quiz.md` |
| Download flashcards | `notebooklm download flashcards cards.json` |
| Download flashcards (markdown) | `notebooklm download flashcards --format markdown cards.md` |
| Download infographic | `notebooklm download infographic ./infographic.png` |
| Delete notebook | `notebooklm notebook delete <id>` |
| List languages | `notebooklm language list` |
| Get language | `notebooklm language get` |
| Set language | `notebooklm language set zh_Hans` |

## Command Output Formats

Commands with `--json` return structured data for parsing.

**Create notebook:**
```
$ notebooklm create "Research" --json
{"id": "abc123de-...", "title": "Research"}
```

**Add source:**
```
$ notebooklm source add "https://example.com" --json
{"source_id": "def456...", "title": "Example", "status": "processing"}
```

**Generate artifact:**
```
$ notebooklm generate audio "Focus on key points" --json
{"task_id": "xyz789...", "status": "pending"}
```

**Chat with references:**
```
$ notebooklm ask "What is X?" --json
{"answer": "X is... [1] [2]", "conversation_id": "...", "turn_number": 1, "is_follow_up": false, "references": [{"source_id": "abc123...", "citation_number": 1, "cited_text": "Relevant passage from source..."}, {"source_id": "def456...", "citation_number": 2, "cited_text": "Another passage..."}]}
```

**Source fulltext:**
```
$ notebooklm source fulltext <source_id> --json
{"source_id": "...", "title": "...", "char_count": 12345, "content": "Full indexed text..."}
```

**JSON list schemas (key fields):**

`notebooklm list --json`:
```json
{"notebooks": [{"id": "...", "title": "...", "created_at": "..."}]}
```

`notebooklm auth check --json`:
```json
{"checks": {"storage_exists": true, "json_valid": true, "cookies_present": true, "sid_cookie": true, "token_fetch": true}, "details": {"storage_path": "...", "auth_source": "file"}}
```

`notebooklm source list --json`:
```json
{"sources": [{"id": "...", "title": "...", "status": "ready|processing|error"}]}
```

`notebooklm artifact list --json`:
```json
{"artifacts": [{"id": "...", "title": "...", "type": "Audio Overview", "status": "in_progress|pending|completed|unknown"}]}
```

**Status values:**
- Sources: `processing` -> `ready` (or `error`)
- Artifacts: `pending` or `in_progress` -> `completed` (or `unknown`)

**Extract IDs:** Parse the `id`, `source_id`, or `task_id` field from JSON output.

## Generation Types

All generate commands support:
- `-s, --source` to use specific source(s) instead of all sources
- `--language` to set output language (defaults to configured language or 'en')
- `--json` for machine-readable output (returns `task_id` and `status`)
- `--retry N` to automatically retry on rate limits with exponential backoff

| Type | Command | Options | Download |
|------|---------|---------|----------|
| Podcast | `generate audio` | `--format [deep-dive\|brief\|critique\|debate]`, `--length [short\|default\|long]` | .mp3 |
| Video | `generate video` | `--format [explainer\|brief]`, `--style [auto\|classic\|whiteboard\|kawaii\|anime\|watercolor\|retro-print\|heritage\|paper-craft]` | .mp4 |
| Slide Deck | `generate slide-deck` | `--format [detailed\|presenter]`, `--length [default\|short]` | .pdf / .pptx |
| Slide Revision | `generate revise-slide "prompt" --artifact <id> --slide N` | `--wait`, `--notebook` | *(re-downloads parent deck)* |
| Infographic | `generate infographic` | `--orientation [landscape\|portrait\|square]`, `--detail [concise\|standard\|detailed]`, `--style [auto\|sketch-note\|professional\|bento-grid\|editorial\|instructional\|bricks\|clay\|anime\|kawaii\|scientific]` | .png |
| Report | `generate report` | `--format [briefing-doc\|study-guide\|blog-post\|custom]`, `--append "extra instructions"` | .md |
| Mind Map | `generate mind-map` | *(sync, instant)* | .json |
| Data Table | `generate data-table` | description required | .csv |
| Quiz | `generate quiz` | `--difficulty [easy\|medium\|hard]`, `--quantity [fewer\|standard\|more]` | .json/.md/.html |
| Flashcards | `generate flashcards` | `--difficulty [easy\|medium\|hard]`, `--quantity [fewer\|standard\|more]` | .json/.md/.html |

## Parallel Safety

The CLI stores notebook context in a shared file (`~/.notebooklm/context.json`). Multiple concurrent agents using `notebooklm use` can overwrite each other's context.

**Solutions for parallel workflows:**
1. **Always use explicit notebook ID** (recommended): Pass `-n <notebook_id>` (for `wait`/`download` commands) or `--notebook <notebook_id>` (for others) instead of relying on `use`
2. **Per-agent isolation:** Set unique `NOTEBOOKLM_HOME` per agent: `export NOTEBOOKLM_HOME=/tmp/agent-$ID`
3. **Use full UUIDs:** Avoid partial IDs in automation (they can become ambiguous)

**Commands supporting `-n` shorthand:** `artifact wait`, `source wait`, `research wait/status`, `download *`. Download commands also support `-a/--artifact`. Other commands use `--notebook`. For chat, use `-c <conversation_id>` to target a specific conversation.

**Partial IDs:** Use first 6+ characters of UUIDs. Must be unique prefix (fails if ambiguous). For automation, prefer full UUIDs to avoid ambiguity.

## Error Handling

**On failure, offer the user a choice:**
1. Retry the operation
2. Skip and continue with something else
3. Investigate the error

**Error decision tree:**

| Error | Cause | Action |
|-------|-------|--------|
| Auth/cookie error | Session expired | Run `notebooklm auth check` then `notebooklm login` |
| "No notebook context" | Context not set | Use `-n <id>` or `--notebook <id>` flag (parallel), or `notebooklm use <id>` (single-agent) |
| "No result found for RPC ID" | Rate limiting | Wait 5-10 min, retry |
| `GENERATION_FAILED` | Google rate limit | Wait and retry later |
| Download fails | Generation incomplete | Check `artifact list` for status |
| Invalid notebook/source ID | Wrong ID | Run `notebooklm list` to verify |
| RPC protocol error | Google changed APIs | May need CLI update |

**Exit codes:**

| Code | Meaning | Action |
|------|---------|--------|
| 0 | Success | Continue |
| 1 | Error (not found, processing failed) | Check stderr, see error table above |
| 2 | Timeout (wait commands only) | Extend timeout or check status manually |

## Processing Times

| Operation | Typical Time | Suggested Timeout |
|-----------|--------------|-------------------|
| Source processing | 30s - 10 min | 600s |
| Research (fast) | 30s - 2 min | 180s |
| Research (deep) | 15 - 30+ min | 1800s |
| Notes | instant | n/a |
| Mind-map | instant (sync) | n/a |
| Quiz, flashcards | 5 - 15 min | 900s |
| Report, data-table | 5 - 15 min | 900s |
| Audio generation | 10 - 20 min | 1200s |
| Video generation | 15 - 45 min | 2700s |

**Polling intervals:** When checking status manually, poll every 15-30 seconds to avoid excessive API calls.

## Known Limitations

**Reliable operations (always work):**
- Notebooks (list, create, delete, rename)
- Sources (add, list, delete)
- Chat/queries
- Mind-map, study-guide, report, data-table generation

**Unreliable operations (may hit rate limits):**
- Audio (podcast) generation
- Video generation
- Quiz and flashcard generation
- Infographic and slide deck generation

**Workaround for rate-limited generation:**
1. Check status: `notebooklm artifact list`
2. Retry after 5-10 minutes
3. Use the NotebookLM web UI as fallback

## Language Configuration

Language setting controls the output language for generated artifacts. It is a **GLOBAL** setting that affects all notebooks.

**Common language codes:**

| Code | Language |
|------|----------|
| `en` | English |
| `zh_Hans` | Simplified Chinese |
| `zh_Hant` | Traditional Chinese |
| `ja` | Japanese |
| `ko` | Korean |
| `es` | Spanish |
| `fr` | French |
| `de` | German |
| `pt_BR` | Portuguese (Brazil) |

**Override per command:** Use `--language` flag on generate commands:
```bash
uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm generate audio --language ja
```

## Troubleshooting

```bash
uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm --help
uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm auth check
uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm auth check --test
uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm --version
```
