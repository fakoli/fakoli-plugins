"""Tests for the projection generator (scripts/generate.py)."""

from __future__ import annotations

import generate


def test_render_carries_do_not_hand_edit_banner(good_ledger: dict) -> None:
    doc = generate.render(good_ledger)

    assert "generated" in doc.lower()
    assert "do not hand-edit" in doc.lower()


def test_render_has_at_a_glance_ledger_table_header(good_ledger: dict) -> None:
    doc = generate.render(good_ledger)

    assert "| ID | Principle | Status | Embodied in |" in doc


def test_render_has_one_detailed_block_per_principle(good_ledger: dict) -> None:
    doc = generate.render(good_ledger)

    for entry in good_ledger["principles"]:
        assert entry["name"] in doc
        assert entry["principle"] in doc
        assert entry["why"] in doc


def test_aspirational_block_shows_open_work_not_placeholder(
    good_ledger: dict,
) -> None:
    doc = generate.render(good_ledger)

    assert "build the aspirational thing" in doc
    # No fabricated embodiment placeholder for the aspirational row.
    assert "N/A" not in doc
    assert "TODO" not in doc


def test_aspirational_ledger_row_has_empty_embodied_cell(good_ledger: dict) -> None:
    """The aspirational row must not invent an 'embodied in' cell value."""
    doc = generate.render(good_ledger)
    lines = [ln for ln in doc.splitlines() if ln.startswith("| P10 ")]

    assert len(lines) == 1
    row = lines[0]
    # Last cell (embodied in) is blank for an aspirational entry.
    cells = [c.strip() for c in row.strip().strip("|").split("|")]
    assert cells[-1] == ""


def test_sort_orders_by_credibility_risk_then_status(good_ledger: dict) -> None:
    """high>med>low, then aspirational>asserted>proven, then numeric id."""
    ordered = generate.sort_principles(good_ledger["principles"])
    ids = [p["id"] for p in ordered]

    # P10 (high, aspirational) before P2 (high, asserted) before P1 (med, proven)
    assert ids == ["P10", "P2", "P1"]


def test_sort_uses_numeric_id_tiebreaker() -> None:
    """P2 must sort before P10 when risk and status are identical."""
    principles = [
        {
            "id": "P10",
            "name": "ten",
            "principle": "x",
            "why": "y",
            "status": "aspirational",
            "credibility_risk": "high",
            "open_work": "w",
        },
        {
            "id": "P2",
            "name": "two",
            "principle": "x",
            "why": "y",
            "status": "aspirational",
            "credibility_risk": "high",
            "open_work": "w",
        },
    ]

    ordered = generate.sort_principles(principles)

    assert [p["id"] for p in ordered] == ["P2", "P10"]


def test_render_is_deterministic(good_ledger: dict) -> None:
    assert generate.render(good_ledger) == generate.render(good_ledger)


def test_committed_doc_matches_committed_data() -> None:
    """The committed doc is the exact projection of the committed seed data."""
    from pathlib import Path

    data_path = Path(generate.DATA_PATH)
    doc_path = Path(generate.DOC_PATH)

    expected = generate.render(generate.load_ledger(data_path))
    committed = doc_path.read_text(encoding="utf-8")

    # Match the validator's staleness check: compare on normalized content so
    # CRLF / trailing-whitespace differences do not cause a confusing failure.
    assert generate.normalize_for_comparison(committed) == generate.normalize_for_comparison(expected)
