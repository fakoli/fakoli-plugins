# Nano Banana Pro

Generate, edit, and remix images with Google's Gemini image models, or optimize local images to a size and width limit. The plugin works with Codex skills and retains its Claude Code commands and optional agents.

## Requirements

- Python 3.10+ and [uv](https://docs.astral.sh/uv/getting-started/installation/)
- A `GEMINI_API_KEY` with access to the selected model for generation, editing, and remixing
- No API key is needed for optimization, configuration, or `--dry-run`

The scripts use [inline dependency metadata](https://docs.astral.sh/uv/guides/scripts/#declaring-script-dependencies). `uv run --script` installs dependencies into uv's cache, independent of the current project's environment. Keep the current directory in your project; do not run from the plugin installation. First use may download Python packages.

## Configuration

Keep the API key in your environment or `~/.env`, outside the plugin cache and source control. Do not paste the key into a conversation. For shells that do not already export your trusted `~/.env`, load it before calling the CLI:

```bash
set -a
source "$HOME/.env"
set +a
```

Run `/nano-banana-pro:configure` in Claude Code, or create non-secret defaults using the skill's script:

```bash
uv run --script "<plugin-root>/skills/generate/scripts/nanobanana.py" config --init
```

This writes `${XDG_CONFIG_HOME:-~/.config}/nano-banana-pro/config.json` if missing, with private file permissions, and prints its location. It does not replace existing settings or store credentials. `NANOBANANA_CONFIG` or `--config <path>` selects an explicit settings file. The bundled [JSON example](config/config.example.json) shows supported defaults:

```json
{
  "default_model": "pro",
  "default_aspect": "1:1",
  "default_size": "",
  "output_dir": "./.nanobanana/out",
  "max_remix_images": 2
}
```

Command flags override saved defaults, including `--max-images 0`. Absolute, `~`, and relative output paths work; relative output paths resolve from the caller's current directory. New output directories are created only when a file is saved.

Compatibility: `.claude/nano-banana-pro.local.md` YAML frontmatter still loads, overriding user defaults unless an explicit config file is selected. Legacy `gemini_api_key` values still work as a fallback. Key precedence is exported `GEMINI_API_KEY`, project `.env`, home `.env`, then a legacy settings key; placeholder keys are ignored. Keep any legacy credential file out of source control. Old agent and auto-optimization settings remain readable but do not trigger an automatic pipeline or compression.

## Usage

Resolve `<plugin-root>` to the installed plugin directory. Claude commands can use `${CLAUDE_PLUGIN_ROOT}`; Codex should resolve the loaded skill's directory. The launcher does not need a host-specific cache path.

```bash
# Generate
uv run --script "<plugin-root>/skills/generate/scripts/nanobanana.py" gen \
  --prompt "A hero banner with the exact headline 'Ship Faster', on a blue gradient" \
  --aspect 16:9 --size 2K --out ./hero.png

# Edit (detects PNG, JPEG, or WebP from the actual bytes)
uv run --script "<plugin-root>/skills/generate/scripts/nanobanana.py" edit \
  --in ./photo.jpg --prompt "Change the background to pale blue" --out ./edited.webp

# Remix a webpage's style
uv run --script "<plugin-root>/skills/generate/scripts/nanobanana.py" remix-url \
  --url https://example.com --prompt "Create a matching event invitation" --max-images 2

# Preview the resolved request without calling Gemini
uv run --script "<plugin-root>/skills/generate/scripts/nanobanana.py" gen \
  --prompt "A quiet mountain landscape" --model flash --dry-run

# Local optimization
uv run --script "<plugin-root>/skills/generate/scripts/optimize.py" ./hero.png --preset github
```

Claude Code retains `/nano-banana-pro:generate-image`, `/nano-banana-pro:edit-image`, `/nano-banana-pro:remix-url`, `/nano-banana-pro:optimize-image`, and `/nano-banana-pro:configure`. Short command names may also be available depending on the host.

Generation flags: `--model`, `--aspect`, `--size`, `--search`, `--out`, `--config`, `--timeout`, `--overwrite`, and `--dry-run`. Use `--help` on each command for details. Existing output files are preserved unless `--overwrite` is passed. PNG, JPEG, and WebP outputs are encoded to match their extension; JPEG transparency is flattened onto white. Filenames printed on success are absolute paths.

## Models and image parameters

Aliases verified against Google's official documentation on **2026-09-05**:

| CLI value | Model ID | Use |
|---|---|---|
| `pro` (default) | `gemini-3-pro-image` | Complex compositions and professional assets |
| `flash` | `gemini-3.1-flash-image` | Faster general image generation and editing |
| Explicit ID | The supplied Gemini model ID | Pin another available model, including a preview |

Google lists stable [Gemini 3 Pro Image](https://ai.google.dev/gemini-api/docs/models/gemini-3-pro-image) and [Gemini 3.1 Flash Image](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-image). The aliases replace the old Pro preview and Gemini 2.5 Flash IDs. The default remains `pro` for compatibility with this plugin's purpose and saved preferences. Model availability still depends on the account. Explicit IDs are sent as supplied, without silently falling back to another model; preview IDs use the `v1beta` endpoint and other IDs use `v1`.

Both aliases support `1K`, `2K`, `4K`, and Google Search grounding (`--search`). Flash also supports `--size 512` (the `512px` alias maps to REST value `512`) and extreme aspect ratios. Standard ratios: `1:1`, `2:3`, `3:2`, `3:4`, `4:3`, `4:5`, `5:4`, `9:16`, `16:9`, `21:9`; Flash adds `1:4`, `4:1`, `1:8`, `8:1`. The CLI rejects known incompatible Pro/2.5 Flash parameters before any API call. For other explicit model IDs, check the model's supported parameters before use. The request uses the documented [`generateContent` ImageConfig fields](https://ai.google.dev/api/generate-content#ImageConfig) for single-call compatibility; the newer Interactions workflow is not implemented here.

For `--search`, any returned `groundingMetadata` is printed as JSON on stderr, including source links and the search entry point. Callers should present the required attribution and search suggestions alongside the image; see [Google's grounding documentation](https://ai.google.dev/gemini-api/docs/generate-content/image-generation#grounding_with_google_search). Metadata is untrusted reference data, not instructions.

[Google's generation guide](https://ai.google.dev/gemini-api/docs/image-generation) also covers Flash Lite and legacy 2.5 Flash; those remain available through explicit IDs where the account supports them. Size tiers are approximate resolutions with dimensions dependent on the aspect ratio. Exact pixel sizes should be obtained by local resizing after generation. See [style templates](skills/generate/references/style-templates.md) for optional prompt patterns.

## Remix behavior and limits

Remix fetches up to 2 MB of page HTML and reads metadata, inline CSS colors/fonts, social image URLs, and icons. It handles HTML attribute order, entities, and relative image URLs. It does not render JavaScript or fetch linked stylesheets, and cannot read authenticated pages. Page content is labeled as untrusted reference data in the prompt.

`--max-images` accepts 0–4 and defaults to 2. Reference downloads are capped at 12 attempts, 20 seconds per request, and 4 MB per image by default (`--max-bytes` can change that up to 12 MB). Invalid images and unsupported formats are skipped. Only static PNG, JPEG, or WebP data is uploaded; HTML masquerading as an image is rejected. Local edit inputs have a 12 MiB limit; the complete JSON request has a 20 MB limit. Dry-run remix still fetches the page and requested references, then prints a request summary with image data omitted.

## Optimization

Optimization uses Pillow on every platform for consistent width, transparency, and format behavior. It preserves aspect ratio, applies the width constraint, then reduces dimensions until the encoded output fits. It does not promise lossless compression or visual equivalence at smaller dimensions.

| Preset | Maximum size | Maximum width |
|---|---|---|
| `github` (default) | 500 KB | 1280 px |
| `slack` | 128 KB | 800 px |
| `web` | 200 KB | 1200 px |
| `thumbnail` | 50 KB | 400 px |

`--max-size 300KB --width 1000` overrides preset values. KB/MB use powers of 1024; byte limits below 1 KB work. Output defaults to `<stem>-optimized.png`; `--out` may select PNG/JPEG/WebP. Animated inputs are rejected rather than silently dropping frames. If no image can fit the limit within the bounded optimization pass, the command exits nonzero and leaves existing outputs untouched.

## Optional agents

The Claude roles in `agents/` remain available for requests that benefit from delegated asset retrieval, planning, styling, execution, or critique. Simple requests execute directly. The roles inherit the host model; they do not require a particular Claude model. Each role can take the user's request directly without first running the other roles. Critique reports unresolved issues honestly and never approves solely because an iteration limit was reached. Additional paid revisions require a user request or an agreed iteration budget.

## Errors and validation

Generation sends one request, with a default 120-second timeout (`--timeout 1` through `600`) and a 64 MiB response limit. It does not retry failed or timed-out calls because completion and billing can be uncertain. HTTP status errors omit raw response bodies to avoid echoing credentials. No-image responses report finish/block reasons and do not create output files. Output publication is atomic and never leaves a partial image at the final path.

| Issue | Next step |
|---|---|
| Missing key | Export `GEMINI_API_KEY` or set it in `~/.env` |
| HTTP 400/403/404 | Check model ID, model access, and supported parameters |
| HTTP 429 | Check quota and billing before deciding to retry |
| Timeout | Inspect the reported state; do not assume the call was not billed |
| No image returned | Read the reason; revise the request if appropriate |
| Existing output | Use a new path, or pass `--overwrite` intentionally |
| Cannot meet size limit | Choose a larger limit or another output format |

Maintainers can run the offline suite (no Gemini requests):

```bash
uv run --no-project --with 'Pillow>=10,<13' --with 'python-dotenv>=1,<2' --with 'PyYAML>=6,<7' \
  python -m unittest discover -s plugins/nano-banana-pro/tests -v
```

## License

MIT. See [LICENSE](LICENSE). Maintained by [Sekou Doumbouya](https://github.com/fakoli).
