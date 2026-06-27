# Testing Guide

## Quick Start

```bash
cd plugins/systems-thinking

# First time setup from the marketplace checkout
uv sync

# Fast tests — no API key needed
uv run pytest tests/unit tests/contracts

# Eval tests — requires claude CLI and ANTHROPIC_API_KEY
uv run pytest tests/evals -m eval
```

## Test Layers

### Unit Tests (`tests/unit/`)

Validate hook prompts, frontmatter parsing, file structure, and internal logic. These run in milliseconds and are fully deterministic. No network calls, no API keys.

### Contract Tests (`tests/contracts/`)

Verify plugin layout conforms to spec: correct directory structure, valid agent/skill definitions, well-formed output contracts. Runs in seconds, deterministic, no external dependencies.

### Eval Tests (`tests/evals/`)

End-to-end scenario tests that invoke Claude CLI with specific prompts and grade the output. These take minutes, cost API credits, and require:

- `@anthropic-ai/claude-code` installed globally (`npm install -g @anthropic-ai/claude-code`)
- `ANTHROPIC_API_KEY` environment variable set

## Running Eval Tests Manually

Eval tests invoke the Claude CLI end-to-end and are **non-deterministic** — they depend on model output, can be slow, and may time out. They should be run manually rather than as part of automated CI gates.

```bash
# Run all eval tests
.venv/bin/python -m pytest tests/evals/ -v

# Run a single eval case
.venv/bin/python -m pytest tests/evals/test_evals.py::test_eval_case[complexity_mapper_basic] -v
.venv/bin/python -m pytest tests/evals/test_evals.py::test_eval_case[decision_brief_basic] -v
.venv/bin/python -m pytest tests/evals/test_evals.py::test_eval_case[hook_enforcement] -v

# With a longer timeout (default is 120s, which may not be enough)
.venv/bin/python -m pytest tests/evals/ -v --timeout=600
```

**Prerequisites:** `claude` CLI installed globally and `ANTHROPIC_API_KEY` set. Eval tests cost API credits.

**Expected behavior:** These tests may fail intermittently due to model output variability or timeouts. A single failure does not indicate a plugin bug — re-run the specific case before investigating.

## Adding New Tests

### Unit and Contract Tests

Add standard pytest functions to the appropriate directory. Follow existing naming conventions (`test_<subject>.py`). No special scaffolding needed — just import pytest and write assertions.

### Eval Tests

1. Create a YAML case file in `tests/evals/cases/`.
2. Add any supporting fixtures (mock repos, sample files) under `tests/evals/fixtures/`.
3. The eval runner picks up new `.yaml` files automatically.

## Eval Case Format

Each YAML case file defines a single evaluation scenario:

```yaml
name: descriptive-kebab-case-name
description: What this eval tests in one sentence.
prompt: |
  The exact prompt sent to Claude CLI.
context:
  files:
    - path: relative/path/to/file.py
      content: |
        File content provided as context.
  working_directory: optional/subdir
expected:
  grader: contains # which grader to use
  criteria:
    - "expected substring" # grader-specific criteria
    - "another expected output"
timeout: 120 # seconds, optional (default: 300)
tags:
  - eval
  - optional-additional-tag
```

### Field Reference

| Field                       | Required | Description                                  |
| --------------------------- | -------- | -------------------------------------------- |
| `name`                      | yes      | Unique identifier for the case               |
| `description`               | yes      | Human-readable summary                       |
| `prompt`                    | yes      | Input sent to Claude CLI                     |
| `context.files`             | no       | Virtual files available during the run       |
| `context.working_directory` | no       | CWD override for the CLI invocation          |
| `expected.grader`           | yes      | Grading strategy to apply                    |
| `expected.criteria`         | yes      | Grader-specific pass/fail criteria           |
| `timeout`                   | no       | Max seconds before the case is marked failed |
| `tags`                      | no       | Pytest markers applied to the case           |

## Eval Metrics Dimensions

Eval cases measure plugin performance across five dimensions:

| Dimension | What It Measures | Graders Used |
|---|---|---|
| **Structural compliance** | Does output follow the output contract? | `section_check`, `markdown_structure` |
| **Evidence quality** | Are findings sourced? Is evidence separated from inference? | `source_anchor_coverage`, `evidence_labels` |
| **Systems thinking adherence** | Does output identify feedback loops, compound failures, leverage points? | `section_check`, `forbidden_patterns` |
| **Analytical completeness** | Did the plugin find specific technical facts from the fixture? | `quantitative_claims` |
| **Operational** | Did it finish? How long? Did it produce output? | `file_exists`, wall-clock time, stdout length |

### Cloud Interconnect Eval Suite

The `cloud_interconnect_*` eval cases use a realistic fixture (`fixtures/cloud_interconnect_vendor_docs.md`) covering six AWS-to-GCP interconnect options with embedded ground truth facts (pricing, limits, SLAs, preview flags).

```bash
# Run the full cloud interconnect suite
.venv/bin/python -m pytest tests/evals/test_evals.py -v -k cloud_interconnect --timeout=600

# Run a single tier
.venv/bin/python -m pytest tests/evals/test_evals.py::test_eval_case[cloud_interconnect_complexity_basic] -v --timeout=300
```

**Tiered cases:**
- **Basic:** `cloud_interconnect_complexity_basic` — does the plugin produce output at all?
- **Structural:** `cloud_interconnect_complexity_structural` — correct headings, evidence labels, no false confidence
- **Technical:** `cloud_interconnect_complexity_technical` — extracts specific quantitative facts
- **Decision brief:** `cloud_interconnect_decision_brief` — two-step workflow produces structured brief
- **Architecture risk:** `cloud_interconnect_arch_risk_review` — identifies risks, dependencies, failure modes

## Graders

| Grader | Behavior | Criteria Format |
|---|---|---|
| `file_exists` | Expected files exist in workdir | `files: [list of paths]` |
| `section_check` | File contains required section keywords | `file`, `sections: [list]` |
| `forbidden_patterns` | File does NOT contain regex patterns | `file`, `patterns: [list]` |
| `markdown_structure` | Markdown file has required headings | `file`, `headings: [list]` |
| `source_anchor_coverage` | Fraction of findings with source references | `file`, `min_coverage: 0.5` |
| `evidence_labels` | Output has evidence and inference labels | `file`, `min_source_labels: 3`, `min_inferred_labels: 1` |
| `quantitative_claims` | Specific quantitative facts appear in output | `file`, `claims: [{pattern, description}]` |
| `cross_reference_consistency` | Terms from one section appear in related sections | `file`, `sections_to_cross_check: [[a, b]]`, `min_overlap: 0.3` |
| `json_schema` | JSON file validates against schema | JSON schema object |
| `composite` | Aggregates multiple grader results | Auto-applied to all cases |

### Adding New Fixtures and Cases

1. Create a fixture file in `tests/evals/fixtures/` with embedded ground truth facts
2. Create a YAML case file in `tests/evals/cases/` referencing the fixture
3. Use `setup` steps to copy fixtures into the workdir
4. Choose graders based on which metric dimensions you want to measure
5. Set appropriate timeouts (basic: 180s, intermediate: 240s, advanced: 300s)

To add a new grader, implement a function in `tests/evals/graders/` following the pattern:
`def grade_<name>(filepath: Path, config: dict) -> dict` returning `{"pass": bool, "score": float, ...}`.
Add the import to `graders/__init__.py` and dispatch branches in both `harness.py` and `test_evals.py`.

## CI Behavior

The marketplace repository runs shared plugin validation on pull requests,
including manifest validation and plugin-change checks. The systems-thinking
unit and contract tests are imported here for local verification and targeted
migration checks:

```bash
uv run pytest tests/unit tests/contracts
```

Eval tests remain manual because they invoke the Claude CLI and can spend API
credits. Run them locally when validating agent behavior.

## Common Issues

**"claude CLI not found"**
Install it: `npm install -g @anthropic-ai/claude-code`. If you only want to run unit/contract tests, skip evals with `pytest tests/unit tests/contracts`.

**"API key not set"**
Eval tests require `ANTHROPIC_API_KEY` in your environment. Unit and contract tests do not need it.

**Frontmatter parse errors**
Agent and skill `.md` files must start with a `---` line and have a matching closing `---`. Check for missing delimiters or leading whitespace before the first `---`.

**Timeout failures in evals**
Default timeout is 300 seconds. If a specific case needs more time, set `timeout` in the YAML case file. For local runs, you can also pass `--timeout=600` to pytest.
