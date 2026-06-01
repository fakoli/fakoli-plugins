#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""generate.py — Project data/principles.json into docs/fakoli-style.md.

The committed doc is a pure, deterministic projection of the seed ledger:
a "generated — do not hand-edit" banner, a preamble, an at-a-glance ledger
table, and one detailed block per principle. Entries are ordered most
load-bearing yet least-proven first (credibility_risk, then status, with a
numeric id tiebreaker so the order is stable and lockable by validate.py).

Invocation:
    uv run --script scripts/generate.py            # write the committed doc
    uv run --script scripts/generate.py --check     # diff without writing

Paths are resolved relative to this script, so it works regardless of CWD.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# --------------------------------------------------------------------------
# Path resolution (relative to this script, never the CWD)
# --------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _SCRIPT_DIR.parent

DATA_PATH: Path = _PLUGIN_ROOT / "data" / "principles.json"
DOC_PATH: Path = _PLUGIN_ROOT / "docs" / "fakoli-style.md"

BANNER = (
    "<!-- generated — do not hand-edit. "
    "Source: data/principles.json. "
    "Regenerate: uv run --script scripts/generate.py -->"
)

# Sort weights: most load-bearing yet least-proven first.
_RISK_RANK = {"high": 0, "med": 1, "low": 2}
_STATUS_RANK = {"aspirational": 0, "asserted": 1, "proven": 2}

_STATUS_LABEL = {
    "proven": "proven",
    "asserted": "asserted",
    "aspirational": "aspirational",
}


# --------------------------------------------------------------------------
# Loading and ordering
# --------------------------------------------------------------------------


def load_ledger(data_path: Path) -> dict:
    """Load the versioned ledger object {version, principles}."""
    return json.loads(data_path.read_text(encoding="utf-8"))


def _numeric_id(entry: dict) -> int:
    """Parse the integer portion of an id like 'P10' -> 10.

    Uses a precise slice (id[1:]) rather than lstrip('P') because lstrip strips
    ALL leading P-characters, which would silently misparse a malformed id like
    'PP10' as 10 instead of raising. The schema constrains ids to ^P[0-9]+$ so
    valid ids always carry exactly one leading 'P'.
    """
    return int(entry["id"][1:])


def sort_principles(principles: list[dict]) -> list[dict]:
    """Order by credibility_risk, then status, then numeric id.

    high > med > low, then aspirational > asserted > proven, then P2 < P10.
    The numeric id tiebreaker guarantees a single stable order that the
    staleness check can lock the committed doc to.
    """
    return sorted(
        principles,
        key=lambda p: (
            _RISK_RANK[p["credibility_risk"]],
            _STATUS_RANK[p["status"]],
            _numeric_id(p),
        ),
    )


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def _embodied_cell(entry: dict) -> str:
    """The 'Embodied in' ledger cell — blank for aspirational entries."""
    embodiments = entry.get("embodied_in")
    if not embodiments:
        return ""
    return "<br>".join(f"`{e['ref']}`" for e in embodiments)


def _ledger_row(entry: dict) -> str:
    status = _STATUS_LABEL[entry["status"]]
    return (
        f"| {entry['id']} | {entry['name']} | {status} | {_embodied_cell(entry)} |"
    )


def _detail_block(entry: dict) -> str:
    lines: list[str] = []
    lines.append(f"### {entry['id']} — {entry['name']}")
    lines.append("")
    lines.append(f"**Status:** {_STATUS_LABEL[entry['status']]}  ")
    lines.append(f"**Credibility risk:** {entry['credibility_risk']}")
    lines.append("")
    lines.append(f"**Principle.** {entry['principle']}")
    lines.append("")
    lines.append(f"**Why.** {entry['why']}")

    proof = entry.get("proof")
    if proof:
        lines.append("")
        lines.append(f"**Proof.** `{proof}`")

    embodiments = entry.get("embodied_in")
    if embodiments:
        lines.append("")
        lines.append("**Embodied in:**")
        lines.append("")
        for e in embodiments:
            lines.append(f"- `{e['ref']}` ({e['plugin']}) — {e['mechanism']}")

    open_work = entry.get("open_work")
    if open_work:
        lines.append("")
        lines.append(f"**Open work.** {open_work}")

    return "\n".join(lines)


def normalize_for_comparison(text: str) -> str:
    """Normalize whitespace so cosmetic differences never trigger a false stale.

    Applied symmetrically to both the committed doc and the freshly rendered
    projection before comparing them:
      - CRLF / CR line endings → LF
      - trailing whitespace stripped from every line
      - trailing blank lines collapsed to a single trailing newline
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    # Collapse trailing blank lines to a single trailing newline.
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def render(ledger: dict) -> str:
    """Render the full markdown projection of the ledger.

    Deterministic: identical input always yields byte-identical output, so
    validate.py can lock the committed doc to this exact projection.
    """
    ordered = sort_principles(ledger["principles"])

    parts: list[str] = []
    parts.append(BANNER)
    parts.append("")
    parts.append("# Fakoli Style — Operating-Model Principles")
    parts.append("")
    parts.append(
        "This ledger is the governed record of the Fakoli Style operating "
        "model. Each principle declares the failure it prevents and an honest "
        "lifecycle status: **proven** (machine-verified), **asserted** "
        "(claimed with a pointer, not yet machine-verified), or "
        "**aspirational** (not yet built)."
    )
    parts.append("")
    parts.append(
        "Entries are ordered most load-bearing yet least-proven first — by "
        "credibility risk, then by status — so the claims that would most "
        "damage the project if false are confronted before the easy wins."
    )
    parts.append("")

    parts.append("## At a glance")
    parts.append("")
    parts.append("| ID | Principle | Status | Embodied in |")
    parts.append("| --- | --- | --- | --- |")
    for entry in ordered:
        parts.append(_ledger_row(entry))
    parts.append("")

    parts.append("## Principles")
    parts.append("")
    for i, entry in enumerate(ordered):
        parts.append(_detail_block(entry))
        if i != len(ordered) - 1:
            parts.append("")

    return "\n".join(parts) + "\n"


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Project data/principles.json into docs/fakoli-style.md.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Diff the projection against the committed doc without writing.",
    )
    opts = parser.parse_args(argv)

    rendered = render(load_ledger(DATA_PATH))

    if opts.check:
        current = DOC_PATH.read_text(encoding="utf-8") if DOC_PATH.exists() else ""
        if normalize_for_comparison(current) != normalize_for_comparison(rendered):
            print(
                f"error: {DOC_PATH} is stale; "
                "run: uv run --script scripts/generate.py",
                file=sys.stderr,
            )
            return 1
        print(f"ok: {DOC_PATH} is up to date")
        return 0

    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_PATH.write_text(rendered, encoding="utf-8")
    print(f"wrote {DOC_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
