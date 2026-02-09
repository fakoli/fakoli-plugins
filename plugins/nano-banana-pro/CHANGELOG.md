# Changelog

All notable changes to the Nano Banana Pro plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
