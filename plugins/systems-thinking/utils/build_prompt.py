#!/usr/bin/env python3
"""Build a complete prompt for a CLI worker by combining an agent definition
with input context.

Usage:
    python3 utils/build_prompt.py --agent caveat-extractor --input sections/003.md
    python3 utils/build_prompt.py --agent caveat-extractor --input sections/003.md sections/007.md --budget 4000
    python3 utils/build_prompt.py --agent caveat-extractor --input sections/003.md -o /tmp/prompt.txt
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Frontmatter / agent parsing
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?\n)---\s*\n", re.DOTALL)


def _parse_agent_file(agent_path: Path) -> tuple[dict[str, str], str]:
    """Read an agent .md file and return (frontmatter_dict, body_markdown).

    The frontmatter is parsed minimally (key: value) without requiring PyYAML.
    Multi-line values using ``>`` or ``|`` are collapsed into a single string.
    """
    text = agent_path.read_text(encoding="utf-8")
    fm: dict[str, str] = {}
    body = text

    match = _FRONTMATTER_RE.match(text)
    if match:
        raw_fm = match.group(1)
        body = text[match.end() :]
        current_key: Optional[str] = None
        for line in raw_fm.splitlines():
            if line.startswith("  ") and current_key is not None:
                # continuation line for a multi-line scalar
                fm[current_key] = (fm[current_key] + " " + line.strip()).strip()
            elif ":" in line:
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip().lstrip(">|").strip()
                fm[key] = value
                current_key = key
            else:
                current_key = None

    return fm, body.strip()


def _auto_detect_agents_dir(override: Optional[Path] = None) -> Path:
    """Locate the agents directory.

    Search order:
    1. Explicit *override* if provided.
    2. Walk upward from this script to find ``agents/``.
    """
    if override is not None:
        return override

    current = Path(__file__).resolve().parent
    for _ in range(10):
        candidate = current / "agents"
        if candidate.is_dir():
            return candidate
        parent = current.parent
        if parent == current:
            break
        current = parent

    # Fallback: relative to script assuming utils/ sits next to agents/.
    fallback = Path(__file__).resolve().parent.parent / "agents"
    return fallback


# ---------------------------------------------------------------------------
# Token estimation (matches index_doc.py heuristic)
# ---------------------------------------------------------------------------


def estimate_tokens(text: str) -> int:
    """Approximate token count: word_count * 1.3, rounded."""
    return round(len(text.split()) * 1.3)


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------


def build_prompt(
    agent_name: str,
    agent_body: str,
    input_contents: list[tuple[str, str]],
    budget: Optional[int] = None,
    extra_context: Optional[str] = None,
) -> str:
    """Assemble the full prompt string.

    Parameters
    ----------
    agent_name:
        Human-readable agent name (from frontmatter or filename).
    agent_body:
        The Markdown body of the agent definition (system prompt).
    input_contents:
        List of (filename, file_text) tuples.
    budget:
        Optional target token budget for the response.
    extra_context:
        Optional additional context (e.g., pattern scan JSON).
    """
    parts: list[str] = []

    parts.append(f"You are acting as the {agent_name} agent.\n")
    parts.append(agent_body)
    parts.append("\n---\n")
    parts.append("## Your Task\n")
    parts.append("Analyze the following input material and produce your findings.\n")

    if extra_context:
        parts.append("### Additional Context\n")
        parts.append(extra_context)
        parts.append("")

    parts.append("### Input Material\n")
    for fname, content in input_contents:
        parts.append(f"#### File: {fname}\n")
        parts.append(content)
        parts.append("")

    parts.append("### Output Requirements\n")
    parts.append("- Write your findings in structured Markdown format")
    parts.append("- Follow the output format specified in your instructions above")
    if budget:
        parts.append(f"- Keep your response under {budget} tokens if specified")
    parts.append("- Include source anchors (filename, line numbers) for every finding")
    parts.append("- If you find nothing noteworthy, say so explicitly -- do not fabricate findings")

    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build a complete prompt for a Claude CLI worker by combining "
            "an agent definition with input context."
        ),
    )
    parser.add_argument(
        "--agent",
        required=True,
        help="Agent name (maps to agents/{name}.md)",
    )
    parser.add_argument(
        "--input",
        nargs="+",
        type=Path,
        required=True,
        dest="input_files",
        help="One or more input files to include in the prompt",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output file for the assembled prompt (default: stdout)",
    )
    parser.add_argument(
        "--budget",
        type=int,
        default=None,
        help="Target token budget for the response",
    )
    parser.add_argument(
        "--context",
        nargs="*",
        type=Path,
        default=None,
        help="Additional context files (e.g., patterns.json from scan_patterns.py)",
    )
    parser.add_argument(
        "--agents-dir",
        type=Path,
        default=None,
        help=(
            "Override path to agents directory "
            "(default: auto-detect agents/ from script location)"
        ),
    )
    args = parser.parse_args()

    # Locate and parse agent file.
    agents_dir = _auto_detect_agents_dir(args.agents_dir)
    agent_path = agents_dir / f"{args.agent}.md"
    if not agent_path.is_file():
        print(
            f"Error: agent file not found: {agent_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    fm, agent_body = _parse_agent_file(agent_path)
    agent_name = fm.get("name", args.agent)

    # Read input files.
    input_contents: list[tuple[str, str]] = []
    total_input_tokens = 0
    for fp in args.input_files:
        if not fp.is_file():
            print(f"Warning: input file not found: {fp}", file=sys.stderr)
            continue
        text = fp.read_text(encoding="utf-8")
        input_contents.append((fp.name, text))
        total_input_tokens += estimate_tokens(text)

    if not input_contents:
        print("Error: no valid input files provided.", file=sys.stderr)
        sys.exit(1)

    # Warn if input exceeds budget.
    if args.budget and total_input_tokens > args.budget:
        print(
            f"Warning: total input tokens ({total_input_tokens}) exceed "
            f"budget ({args.budget}). Consider prioritizing files with "
            f"flagged sections or reducing input.",
            file=sys.stderr,
        )

    # Read optional context files.
    extra_context: Optional[str] = None
    if args.context:
        ctx_parts: list[str] = []
        for cp in args.context:
            if cp.is_file():
                ctx_parts.append(f"**{cp.name}:**\n```\n{cp.read_text(encoding='utf-8')}\n```\n")
            else:
                print(f"Warning: context file not found: {cp}", file=sys.stderr)
        if ctx_parts:
            extra_context = "\n".join(ctx_parts)

    prompt = build_prompt(
        agent_name=agent_name,
        agent_body=agent_body,
        input_contents=input_contents,
        budget=args.budget,
        extra_context=extra_context,
    )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(prompt, encoding="utf-8")
        print(f"Prompt written to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(prompt)


if __name__ == "__main__":
    main()
