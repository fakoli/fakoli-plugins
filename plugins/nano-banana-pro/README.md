# Nano Banana Pro

Generate, edit, and remix images using Google's Gemini 3 Pro Image Preview model.

## Features

- **Generate** images from text prompts with precise control over composition
- **Edit** existing images with natural language instructions
- **Remix** webpages into brand-aligned visual assets
- **Optimize** images for GitHub, Slack, web with smart presets
- **Style templates** for common use cases (UI, marketing, artistic)

## Installation

### Requirements

- Python 3.10 or later
- [uv](https://github.com/astral-sh/uv) package manager
- Google AI API key with Gemini 3 Pro access

### Setup

1. Install the plugin in Claude Code
2. Configure your API key (see Configuration section)

## Configuration

Run `/configure` to set up your configuration interactively, or create a settings file manually at `.claude/nano-banana-pro.local.md`:

```markdown
---
gemini_api_key: "your-api-key-here"
default_model: "pro"
default_aspect: "16:9"
default_size: "2K"
output_dir: "./.nanobanana/out"
auto_optimize: "true"
optimize_preset: "github"
max_remix_images: "2"
agent_retriever: "true"
agent_planner: "true"
agent_stylist: "true"
agent_visualizer: "true"
agent_critic: "true"
critic_max_rounds: "3"
---

# Nano Banana Pro Settings

Your local configuration for image generation.
```

An example template is included at `config/nano-banana-pro.example.md`.

### Settings Reference

| Setting | Values | Default | Description |
|---------|--------|---------|-------------|
| `gemini_api_key` | string | — | Google AI API key |
| `default_model` | `pro`, `flash` | `pro` | Gemini model selection |
| `default_aspect` | `1:1`, `16:9`, `4:3`, `9:16`, `3:2` | `1:1` | Default aspect ratio |
| `default_size` | `1K`, `2K`, `4K`, `""` | `""` | Default size tier |
| `output_dir` | path | `./.nanobanana/out` | Output directory |
| `auto_optimize` | `true`, `false` | `true` | Auto-suggest optimization for large images |
| `optimize_preset` | `github`, `slack`, `web`, `thumbnail` | `github` | Default optimization preset |
| `max_remix_images` | integer | `2` | Max reference images for remix mode |
| `agent_retriever` | `true`, `false` | `true` | Enable Retriever agent |
| `agent_planner` | `true`, `false` | `true` | Enable Planner agent |
| `agent_stylist` | `true`, `false` | `true` | Enable Stylist agent |
| `agent_visualizer` | `true`, `false` | `true` | Enable Visualizer agent |
| `agent_critic` | `true`, `false` | `true` | Enable Critic agent |
| `critic_max_rounds` | `1`, `2`, `3` | `3` | Max critic refinement iterations |

### Alternative: Environment Variables

Set `GEMINI_API_KEY` in your environment or in a `.env` file:

```bash
export GEMINI_API_KEY="your-api-key-here"
```

Or create a `.env` file:

```
GEMINI_API_KEY="your-api-key-here"
```

## Usage

### Commands

| Command | Description |
|---------|-------------|
| `/generate-image` | Generate an image from a text prompt |
| `/edit-image` | Edit an existing image with instructions |
| `/remix-url` | Create an image styled from a webpage |
| `/optimize-image` | Reduce image size for GitHub, Slack, web |
| `/configure` | Set up or update plugin configuration |

### Configure

```
/configure              # Full setup wizard
/configure api-key      # Just configure API key
/configure model        # Just configure model selection
/configure agents       # Enable/disable PaperBanana agents
```

### Generate Image

```
/generate-image "A hero banner with bold headline 'Ship Faster' on blue gradient background" --aspect 16:9 --size 2K
```

### Edit Image

```
/edit-image ./banner.png "Increase headline size by 15%, add subtle drop shadow"
```

### Remix URL

```
/remix-url https://stripe.com "Create a hero banner for payments feature with headline 'Accept Anywhere'" --aspect 16:9
```

### Optimize Image

```
/optimize-image ./banner.png --preset github
```

#### Optimization Presets

| Preset | Max Size | Max Width | Use Case |
|--------|----------|-----------|----------|
| `github` | 500KB | 1280px | README images, PR screenshots |
| `slack` | 128KB | 800px | Slack/Discord messages |
| `web` | 200KB | 1200px | Blog posts, documentation |
| `thumbnail` | 50KB | 400px | Previews, icons |

Custom options: `--max-size 300KB --width 1000`

## Style Templates

The plugin includes pre-built prompt templates for common use cases:

### UI/Web Styles
- Hero banners (16:9, 1920x1080)
- Social media cards (1:1, 1200x1200)
- App screenshots (9:16, 1080x1920)
- Landing page sections (4:3)
- Icons (1:1, 512x512)

### Marketing Styles
- Product photography
- Ad creatives
- Logo variations
- Brand assets

### Artistic Styles
- Flat design illustrations
- Abstract art
- Photo-realistic
- Minimalist
- Retro/vintage

See `skills/generate/references/style-templates.md` for detailed templates.

## Aspect Ratios

| Ratio | Best For |
|-------|----------|
| `1:1` | Social avatars, icons, thumbnails |
| `16:9` | Hero banners, presentations, YouTube |
| `4:3` | Product shots, traditional photos |
| `9:16` | Mobile stories, vertical banners |
| `3:2` | Photography, print media |

## Size Options

| Size | Resolution | Use Case |
|------|------------|----------|
| `1K` | ~1024px | Quick previews, drafts |
| `2K` | ~2048px | Web-ready, social media |
| `4K` | ~4096px | Print, high-resolution |

## Model Selection

Choose between two Gemini models:

| Model | ID | Strengths | Best For |
|-------|----|-----------|----------|
| `pro` | Gemini 3 Pro | Higher quality, better text rendering | Final assets, detailed compositions |
| `flash` | Gemini 2.0 Flash | Faster generation | Quick drafts, iteration |

Set your default model in configuration (`default_model`) or override per-command with `--model`:

```
/generate-image "A hero banner" --model flash
```

## PaperBanana Agents

Nano Banana Pro includes a 5-agent pipeline inspired by [Google's PaperBanana framework](https://www.marktechpost.com/2026/02/07/google-ai-introduces-paperbanana-an-agentic-framework-that-automates-publication-ready-methodology-diagrams-and-statistical-plots/) for producing publication-ready visuals.

### Pipeline Architecture

**Phase 1 — Planning** (sequential):

1. **Retriever** — Scans your project for brand assets, colors, fonts, and reference images
2. **Planner** — Transforms your request into a detailed visual specification (layout, components, hierarchy)
3. **Stylist** — Applies aesthetic guidelines: exact colors, typography, mood, and design principles

**Phase 2 — Refinement** (iterative loop, up to 3 rounds):

4. **Visualizer** — Executes image generation using `nanobanana.py` (the only agent that creates files)
5. **Critic** — Evaluates the output on faithfulness, conciseness, readability, and aesthetics; recommends APPROVE or REVISE

### Agent Configuration

Each agent can be enabled/disabled individually in your settings file:

```yaml
agent_retriever: "true"
agent_planner: "true"
agent_stylist: "true"
agent_visualizer: "true"
agent_critic: "true"
critic_max_rounds: "3"
```

When an agent is disabled, the pipeline skips that phase. The Visualizer is always required for image generation.

### How It Works

The agents are orchestrated via Claude Code's Task tool. When you request an image:
1. The Retriever searches your codebase for brand context
2. The Planner creates a visual specification from your request + context
3. The Stylist refines the spec into a polished generation prompt
4. The Visualizer generates the image
5. The Critic evaluates the result and may request up to 3 revision rounds

## Best Practices

1. **Prompt like a designer** - Include layout, margins, typography, and exact text
2. **Lock down text** - Say "Render this text verbatim" for exact copy
3. **Iterate surgically** - Use edit mode for specific refinements
4. **Use templates** - Reference style templates for consistent results

## Output

Generated images are saved to `./.nanobanana/out/` by default with timestamp-based filenames. Use `--out` to specify a custom path.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| 401/403 error | Check API key configuration |
| No image returned | Prompt may have been blocked; try rephrasing |
| Slow generation | Reduce size from 4K to 2K |
| Permission denied | Ensure `uv` and `python3` are in PATH |

## License

MIT License - see [LICENSE](LICENSE) for details.

## Author

Sekou Doumbouya ([@fakoli](https://github.com/fakoli))
