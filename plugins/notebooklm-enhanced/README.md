# NotebookLM Enhanced

Comprehensive Google NotebookLM automation plugin for Claude Code. Create notebooks, add sources, generate podcasts/videos/quizzes/slides, and run multi-notebook research workflows -- all through conversational commands backed by the NotebookLM RPC API.

## What This Plugin Does

This plugin wraps the `notebooklm-py` CLI to give Claude Code full programmatic access to Google NotebookLM, including features not exposed in the web UI:

- **Notebook management**: Create, list, delete, and switch between notebooks
- **Source ingestion**: Add URLs, PDFs, YouTube videos, and local files as sources
- **AI querying**: Ask questions with cited answers from your sources
- **Artifact generation**: Generate podcasts, videos, slide decks, quizzes, flashcards, reports, mind maps, data tables, and infographics
- **Web research**: Automated source discovery via NotebookLM's built-in research feature
- **Cross-notebook synthesis**: Compare and synthesize findings across multiple notebooks

## Prerequisites

- **Python 3.10+**
- **uv** (Python package manager) -- install with `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Google account** with access to [NotebookLM](https://notebooklm.google.com/)
- **notebooklm-py** package (installed automatically via the plugin's `scripts/pyproject.toml`)

## Installation

### Option 1: Clone and symlink

```bash
# Clone the fakoli-plugins repository
git clone https://github.com/fakoli-plugins/fakoli-plugins.git

# Symlink the plugin into your Claude Code plugins directory
ln -s /path/to/fakoli-plugins/plugins/notebooklm-enhanced ~/.claude/plugins/notebooklm-enhanced
```

### Option 2: Add to Claude Code settings

Add to your `.claude/settings.json`:

```json
{
  "plugins": [
    "/path/to/fakoli-plugins/plugins/notebooklm-enhanced"
  ]
}
```

## Quick Start

### 1. Authenticate

```
/notebooklm-enhanced:setup
```

This opens a browser for Google OAuth and verifies your session.

### 2. Create a notebook

```
/notebooklm-enhanced:create-notebook "My Research Topic"
```

### 3. Add sources

```
/notebooklm-enhanced:add-source https://arxiv.org/pdf/2301.00001.pdf
/notebooklm-enhanced:add-source https://www.youtube.com/watch?v=example
/notebooklm-enhanced:add-source ./local-document.pdf
```

### 4. Query your sources

```
/notebooklm-enhanced:query What are the main findings?
```

### 5. Generate artifacts

```
/notebooklm-enhanced:generate audio
/notebooklm-enhanced:generate slide-deck --download ./slides.pdf
/notebooklm-enhanced:generate report --format study-guide
```

### One-step research

```
/notebooklm-enhanced:research "quantum computing applications in healthcare"
```

This creates a notebook, finds sources via web research, synthesizes findings, and generates a report -- all in one command.

## Available Commands

| Command | Description |
|---------|-------------|
| `/notebooklm-enhanced:setup` | Authenticate with Google and verify CLI access |
| `/notebooklm-enhanced:create-notebook` | Create a new notebook, optionally with initial sources |
| `/notebooklm-enhanced:add-source` | Add a URL, file, or YouTube video as a source |
| `/notebooklm-enhanced:query` | Ask questions with cited answers from notebook sources |
| `/notebooklm-enhanced:generate` | Generate artifacts (audio, video, slides, quiz, report, etc.) |
| `/notebooklm-enhanced:library` | Browse notebooks, sources, and artifacts; set active notebook |
| `/notebooklm-enhanced:research` | End-to-end research workflow with web source discovery |

## Skills

### notebooklm-research

Multi-notebook research synthesis skill. Activates when you need to:

- Compare findings across multiple notebooks
- Run cross-notebook analysis
- Perform deep research workflows
- Synthesize information from diverse sources

**Trigger phrases**: "compare across notebooks", "research synthesis", "cross-reference", "deep research on..."

## Agent

### research-agent

Autonomous research agent that handles the full pipeline without user intervention:

1. Creates a notebook for the topic
2. Discovers and adds sources via web research
3. Waits for source processing
4. Runs synthesis queries
5. Generates the requested artifact (report, podcast, slides, etc.)
6. Downloads the result

The agent is triggered automatically when the research skill determines the workflow should run autonomously.

## CLI Reference

All commands use the prefix:

```bash
uv run --project "${CLAUDE_PLUGIN_ROOT}/scripts" notebooklm ...
```

### Core Commands

| Task | CLI Command |
|------|-------------|
| Login | `notebooklm login` |
| Check status | `notebooklm status` |
| List notebooks | `notebooklm list --json` |
| Create notebook | `notebooklm create "Title" --json` |
| Set active notebook | `notebooklm use <id>` |
| Add source | `notebooklm source add "url" --json` |
| List sources | `notebooklm source list --json` |
| Query | `notebooklm ask "question" --json` |
| Web research | `notebooklm source add-research "query" --mode deep --no-wait` |
| Wait for research | `notebooklm research wait --import-all` |

### Generation Commands

| Type | Command | Download |
|------|---------|----------|
| Podcast | `notebooklm generate audio` | `download audio ./out.mp3` |
| Video | `notebooklm generate video` | `download video ./out.mp4` |
| Slide Deck | `notebooklm generate slide-deck` | `download slide-deck ./out.pdf` |
| Report | `notebooklm generate report --format briefing-doc` | `download report ./out.md` |
| Quiz | `notebooklm generate quiz` | `download quiz ./out.json` |
| Flashcards | `notebooklm generate flashcards` | `download flashcards ./out.md` |
| Mind Map | `notebooklm generate mind-map` | `download mind-map ./out.json` |
| Data Table | `notebooklm generate data-table "desc"` | `download data-table ./out.csv` |
| Infographic | `notebooklm generate infographic` | `download infographic ./out.png` |

## License

MIT
