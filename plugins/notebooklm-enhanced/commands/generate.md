---
description: Generate NotebookLM artifacts — podcasts, videos, slide decks, quizzes, reports, mind maps, flashcards, infographics, and data tables
allowed-tools: Bash
---

# Generate NotebookLM Artifact

Generate an artifact from the active notebook's sources.

## Arguments

Parse from: `$ARGUMENTS`

Required:
- Artifact type: `audio`, `video`, `slide-deck`, `quiz`, `report`, `mind-map`, `data-table`, `flashcards`, `infographic`

Options:
- `--instructions "..."`: Custom instructions for generation
- `--source <id>`: Use specific source(s) instead of all — can be repeated
- `--notebook <id>`: Target a specific notebook
- `--format <fmt>`: Output format (varies by type, see table below)
- `--download <path>`: Automatically download when ready
- `--no-wait`: Start generation but don't wait for completion

## Artifact Types and Options

| Type | Command | Formats | Estimated Time | Download Extension |
|------|---------|---------|----------------|--------------------|
| Podcast | `generate audio` | `deep-dive`, `brief`, `critique`, `debate` | 10-20 min | .mp3 |
| Video | `generate video` | `explainer`, `brief` | 15-45 min | .mp4 |
| Slide Deck | `generate slide-deck` | `detailed`, `presenter` | 5-15 min | .pdf, .pptx |
| Infographic | `generate infographic` | orientation: `landscape`, `portrait`, `square` | 5-15 min | .png |
| Report | `generate report` | `briefing-doc`, `study-guide`, `blog-post`, `custom` | 5-15 min | .md |
| Mind Map | `generate mind-map` | *(sync, instant)* | Instant | .json |
| Data Table | `generate data-table` | *(description required)* | Instant | .csv |
| Quiz | `generate quiz` | difficulty: `easy`, `medium`, `hard` | 5-15 min | .json, .md |
| Flashcards | `generate flashcards` | difficulty: `easy`, `medium`, `hard` | 5-15 min | .json, .md |

## Workflow

1. **Verify active notebook**:
   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm status
   ```

2. **Start generation**:
   ```bash
   # Podcast
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm generate audio "Focus on the main arguments" --json

   # Video
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm generate video --json

   # Slide deck
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm generate slide-deck --format detailed --json

   # Report
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm generate report --format briefing-doc --json

   # Quiz
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm generate quiz --difficulty medium --json

   # Flashcards
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm generate flashcards --json

   # Mind map (sync — returns immediately)
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm generate mind-map --json

   # Data table (requires description)
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm generate data-table "Compare key metrics across studies" --json

   # Infographic
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm generate infographic --orientation landscape --json

   # With specific sources
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm generate audio -s SRC_ID1 -s SRC_ID2 --json
   ```

3. **Parse response**: Extract `task_id` and `status`:
   ```json
   {"task_id": "xyz789...", "status": "pending"}
   ```

4. **Wait for completion** (unless `--no-wait` or sync artifact):
   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm artifact wait TASK_ID
   ```

5. **Download** (if `--download` specified):
   ```bash
   # Audio
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm download audio ./output.mp3

   # Video
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm download video ./output.mp4

   # Slide deck
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm download slide-deck ./slides.pdf

   # Report
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm download report ./report.md

   # Quiz
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm download quiz ./quiz.json

   # Flashcards
   uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm download flashcards ./cards.md --format markdown
   ```

6. **Report**: Tell the user the artifact type, status, task ID, and download path if applicable.

## Example Usage

```
/notebooklm-enhanced:generate audio
/notebooklm-enhanced:generate video --instructions "Focus on chapter 3"
/notebooklm-enhanced:generate slide-deck --format presenter --download ./slides.pptx
/notebooklm-enhanced:generate report --format study-guide
/notebooklm-enhanced:generate quiz --difficulty hard
/notebooklm-enhanced:generate mind-map
/notebooklm-enhanced:generate infographic --download ./infographic.png
```

## Notes

- Audio and video generation can take several minutes. The `artifact wait` command will block until complete.
- Mind maps and data tables are synchronous — they return instantly.
- Rate limiting may occur with rapid successive generations. The CLI supports `--retry N` for automatic backoff.
- Always check `notebooklm artifact list` to see status of all artifacts.
