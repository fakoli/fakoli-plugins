# Changelog

All notable changes to the Nano Banana Pro plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

- Stdlib-only Python CLI (no external dependencies)
- Multiple API key sources (settings file, env var, .env files)
- Webpage style extraction (colors, fonts, reference images)
- Theme color, palette, and typography hint extraction
- Reference image downloading for remix mode
