# macOS `say` Command — TTS CLI Reference

## Overview

The macOS `say` command is a built-in CLI tool that converts text to speech using the
Speech Synthesis Manager. It can play audio through the system output device or write
it to an audio file. It is entirely free and requires no API key, network access, or
external service.

- **Cost:** Free (built-in to macOS, no usage limits)
- **Platform:** macOS only (Darwin). Not available on Linux or Windows.
- **Availability:** Ships with every macOS installation; no install step required.

---

## Command Syntax

### Speak text aloud (no file output)

```sh
say [-v <voice>] [-r <rate>] <text>
```

### Write audio to a file

```sh
say -v <voice> -o <outfile> <text>
say -v <voice> -o <outfile> -f <input-text-file>
```

### Read text from stdin

```sh
echo "Hello world" | say -v Samantha -o /tmp/out.aiff
```

---

## Flags

| Flag | Long form | Description |
|------|-----------|-------------|
| `-v <voice>` | `--voice=<voice>` | Select a voice by name. Use `'?'` to list all installed voices. |
| `-r <rate>` | `--rate=<rate>` | Speech rate in words per minute. Default is voice-dependent (~175–200 wpm). Lower = slower; higher = faster. |
| `-o <file>` | `--output-file=<file>` | Write audio to a file instead of (or in addition to) playing it. |
| `-f <file>` | `--input-file=<file>` | Read text to speak from a file. Use `-` to read from stdin. |
| `--file-format=<fmt>` | | Output container format: `AIFF`, `caff`, `m4af`, `WAVE`. Use `'?'` to list all writable formats. |
| `--data-format=<fmt>` | | Audio encoding: `aac`, `alac`, or linear PCM (e.g., `LEF32@22050`). Use `'?'` to list formats for a given container. |
| `--bit-rate=<rate>` | | Bit rate for compressed formats like AAC. Use `'?'` to list valid rates. |
| `--channels=<n>` | | Number of output channels (most voices produce mono only). |
| `--quality=<0-127>` | | Audio converter quality level (0 = lowest, 127 = highest). |
| `--progress` | | Display a progress meter during synthesis. |
| `-i` | `--interactive` | Print text line-by-line with word highlighting during playback. |

---

## Listing Available Voices

```sh
say -v '?'
```

Note: the `?` must be quoted to prevent shell glob expansion.

### Output format

Each line has three fields separated by whitespace:

```
<VoiceName>         <lang_LOCALE>    # <sample sentence>
```

Examples:

```
Samantha            en_US    # Hello! My name is Samantha.
Daniel              en_GB    # Hello! My name is Daniel.
Karen               en_AU    # Hello! My name is Karen.
Alice               it_IT    # Ciao! Mi chiamo Alice.
Eddy (English (US)) en_US    # Hello! My name is Eddy.
```

### Parsing rules

- **Voice name**: everything up to the first column of whitespace before the locale.
  Names containing spaces or parentheses (e.g., `Eddy (English (US))`) must be quoted
  when passed to `-v`.
- **Locale**: ISO format `<language>_<REGION>` (e.g., `en_US`, `fr_FR`, `zh_CN`).
- **Sample**: the text after `# ` is the voice's own sample sentence (not a comment in
  the shell sense — it is part of the output line).

### Programmatic filtering (shell)

```sh
# All US English voices
say -v '?' | grep "en_US"

# All voices for a given language prefix
say -v '?' | grep "^fr_"

# Extract just voice names
say -v '?' | awk '{print $1}'
```

---

## Output Formats

### Default: AIFF

When `-o` is used without `--file-format`, the output is **AIFF** (IFF/AIFF-C
compressed audio). This is supported by all built-in voices.

```sh
say -v Samantha -o /tmp/output.aiff "Hello world"
# file /tmp/output.aiff → IFF data, AIFF-C compressed audio
```

### Other formats (macOS 10.6+)

The file format can be inferred from the output file extension:

| Extension | Format |
|-----------|--------|
| `.aiff` | AIFF (default) |
| `.wav` | WAVE (PCM) |
| `.caf` | Core Audio Format |
| `.m4a` | MPEG-4 / AAC or ALAC |
| `.aac` | AAC audio |

```sh
# WAV output
say -v Samantha -o /tmp/output.wav "Hello world"

# AAC (M4A)
say -v Samantha -o /tmp/output.m4a "Hello world"

# ALAC (lossless inside M4A)
say -v Samantha -o /tmp/output.m4a --data-format=alac "Hello world"

# Core Audio Format with raw float PCM at 8 kHz
say -v Samantha -o /tmp/output.caf --data-format=LEF32@8000 "Hello world"

# List all writable container formats
say --file-format='?'

# List data formats for CAF container
say --file-format=caff --data-format='?'
```

---

## Speech Rate (`-r`)

```sh
say -v Samantha -r 150 "Speak slowly"
say -v Samantha -r 300 "Speak quickly"
```

- Unit: **words per minute**
- Typical default: ~175–200 wpm (voice-dependent)
- Useful range: 80 (very slow) to 500 (very fast)
- No documented hard maximum; extremely high values may distort synthesis

---

## Text Length Limits

No documented hard limit on text length. In practice:

- The `-f` flag (file input) is the recommended approach for long texts.
- Very large command-line strings may hit shell argument length limits (`ARG_MAX`,
  typically ~256 KB on macOS), so use `-f` for anything beyond a few hundred words.
- There is no per-sentence or per-word truncation by the synthesizer itself.

```sh
# For long text, use a file
say -v Samantha -o /tmp/output.aiff -f /path/to/long-script.txt
```

---

## Recommended Voices (This System)

184 voices are installed. The following are high-quality voices recommended for
English TTS use cases:

### US English (`en_US`) — natural-sounding

| Voice name | Notes |
|------------|-------|
| `Samantha` | Default macOS system voice; clear, neutral female |
| `Reed (English (US))` | Modern neural-style male voice |
| `Rocko (English (US))` | Modern neural-style male voice |
| `Eddy (English (US))` | Modern neural-style male voice |
| `Flo (English (US))` | Modern neural-style female voice |
| `Sandy (English (US))` | Modern neural-style female voice |
| `Shelley (English (US))` | Modern neural-style female voice |
| `Grandma (English (US))` | Older female character voice |
| `Grandpa (English (US))` | Older male character voice |
| `Fred` | Classic macOS robotic male voice |

### Other English locales

| Voice name | Locale | Notes |
|------------|--------|-------|
| `Daniel` | `en_GB` | British male; high quality |
| `Karen` | `en_AU` | Australian female |
| `Moira` | `en_IE` | Irish female |
| `Tessa` | `en_ZA` | South African female |
| `Rishi` | `en_IN` | Indian English male |

### Usage note for multi-word voice names

Voice names containing spaces or parentheses must be quoted:

```sh
say -v 'Eddy (English (US))' "Hello"
say -v 'Reed (English (US))' "Hello"
say -v 'Flo (English (US))' "Hello"
```

Single-word names do not require quoting:

```sh
say -v Samantha "Hello"
say -v Daniel "Hello"
```

---

## Practical Examples

```sh
# Speak to speaker
say "Your build is complete"

# Write to AIFF with custom rate
say -v Samantha -r 160 -o /tmp/narration.aiff "Welcome to Fakoli."

# Write to WAV
say -v Daniel -o /tmp/narration.wav "This is a test."

# Write to AAC
say -v Samantha -o /tmp/narration.m4a "Compressed audio output."

# Use a text file as input
say -v Samantha -o /tmp/chapter1.aiff -f /tmp/chapter1.txt

# List all installed voices
say -v '?'

# List US English voices only
say -v '?' | grep "en_US"

# Check exit status (0 = success)
say -v Samantha -o /tmp/test.aiff "test" && echo "OK" || echo "FAILED"
```

---

## Return Values

| Exit code | Meaning |
|-----------|---------|
| `0` | Text was spoken / file was written successfully |
| non-zero | Error; diagnostic message printed to stderr |

---

## Integration Notes

- The command blocks until synthesis is complete (synchronous by default).
- For non-blocking use, run in the background: `say "done" &`
- AIFF output is uncompressed by default and may be large; use `.m4a` or `.wav` for
  smaller files.
- The output sample rate depends on the voice; it cannot always be overridden without
  resampling artifacts.
- `say` has no concurrency limit — multiple instances can run simultaneously.
- Voices listed by `say -v '?'` reflect only voices installed on the current system;
  the set varies by macOS version and user-installed voice packs.
