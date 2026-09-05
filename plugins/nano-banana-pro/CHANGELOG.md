# Changelog

All notable changes to the Nano Banana Pro plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.0] - 2026-09-05

### Added

- Native Codex plugin manifest alongside Claude command and agent compatibility.
- Self-contained uv scripts, a non-secret user configuration initializer, explicit model IDs, and request dry-runs.
- Offline regression coverage for configuration precedence, image MIME/format handling, remix extraction, bounded failures, and optimizer constraints.

### Changed

- `pro` and `flash` now resolve to Google's documented stable `gemini-3-pro-image` and `gemini-3.1-flash-image` IDs. Pro remains the default; explicit model IDs preserve pinning options.
- Image generation makes one bounded request without automatic retries or mandatory agent pipelines. Optional agents inherit the host model and report unresolved critique honestly.
- Optimization uses Pillow consistently across platforms and reports failure when constraints cannot be met.
- New defaults live under the user's configuration directory; legacy project settings remain readable. Credentials stay in the environment or `.env` files outside the install cache.

### Fixed

- Isolated dependency execution from arbitrary working directories without changing where outputs are saved.
- Correct absolute/tilde output paths, explicit remix flag precedence, input MIME detection, HTML metadata attribute order, and full CSS hex colors.
- Skip thought images when choosing the final result; validate and atomically encode PNG/JPEG/WebP outputs without clobbering files by default.
- Preserve source assets, reject animation flattening, honor byte limits below 1 KB, and avoid false optimization success.
- Removed credential-file scans from the brand retriever and narrowed optional agent responsibilities.

## [1.3.4] - 2026-06-26

### Fixed

- Renamed agent frontmatter `allowed-tools` keys to `tools` so tool restrictions are honored.
- Normalized command frontmatter to `argument-hint`.
- Normalized skill `allowed-tools` frontmatter to the marketplace schema.
- Synced package metadata and changelog with the current marketplace release.

## [1.3.0] - 2026-02-08

### Added

- **PaperBanana Agents** — 5-agent pipeline for automated, high-quality image creation
  - **Retriever** — Scans project for brand assets, colors, fonts, and references
  - **Planner** — Transforms requests into detailed visual specifications
  - **Stylist** — Applies aesthetic guidelines, colors, typography, and design principles
  - **Visualizer** — Executes image generation (the only agent that creates files)
  - **Critic** — Evaluates output on faithfulness, conciseness, readability, aesthetics (up to 3 refinement rounds)
- **Configure command** (`/configure`) — Interactive setup wizard for API key, defaults, and agents
- **Model selection** — `--model pro` (Gemini 3 Pro) or `--model flash` (Gemini 2.5 Flash Image)
- Example configuration template (`config/nano-banana-pro.example.md`)
- New settings: `default_model`, `auto_optimize`, `optimize_preset`, `max_remix_images`, agent toggles, `critic_max_rounds`

### Changed

- `nanobanana.py` — Replaced hardcoded model/endpoint with `MODEL_MAP` and dynamic `get_endpoint()`
- Remix mode respects `max_remix_images` setting from configuration

## [1.2.0] - 2026-02-01

### Added

- **Optimize command** (`/optimize-image`) - Reduce image size for GitHub, Slack, web
- Named presets: `github` (500KB), `slack` (128KB), `web` (200KB), `thumbnail` (50KB)
- Custom size constraints: `--max-size` and `--width` options
- Cross-platform support: `sips` on macOS, Pillow on other platforms
- Auto-suggestion guidance: Claude suggests optimization for large images (>500KB)

### Changed

- Pillow added as conditional dependency (non-macOS only)

## [1.1.0] - 2026-02-01

### Changed

- Use `python-dotenv` library instead of custom .env parsing for better reliability
- Simplified SKILL.md (169 → 31 lines) - now links to README as authoritative source
- Reduced command file duplication by linking to README for configuration docs
- Extracted `process_and_save_result()` helper to reduce code repetition

### Fixed

- Pyright warning about optional subscript in icon_urls handling

## [1.0.0] - 2025-02-01

### Added

- Initial release as a marketplace plugin
- **Generate command** (`/generate-image`) - Create images from text prompts
- **Edit command** (`/edit-image`) - Modify existing images with natural language
- **Remix URL command** (`/remix-url`) - Generate images styled from webpages
- **Settings file support** - Configure API key and defaults via `.claude/nano-banana-pro.local.md`
- **Style templates** - Pre-built prompt patterns for UI, marketing, and artistic styles
- Support for aspect ratios: 1:1, 16:9, 4:3, 9:16, 3:2
- Support for size tiers: 1K, 2K, 4K
- Automatic output directory management (`.nanobanana/out/`)
- Google Search grounding option (`--search` flag)

### Features from Original Skill

- Lightweight Python CLI (single dependency: python-dotenv)
- Multiple API key sources (settings file, env var, .env files)
- Webpage style extraction (colors, fonts, reference images)
- Theme color, palette, and typography hint extraction
- Reference image downloading for remix mode
