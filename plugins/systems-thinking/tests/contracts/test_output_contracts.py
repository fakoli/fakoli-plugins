"""Tests that docs/output-contracts.md defines all five output contracts."""

import pytest

from tests.conftest import PLUGIN_ROOT

CONTRACTS_PATH = PLUGIN_ROOT / "docs" / "output-contracts.md"


@pytest.fixture
def contracts_text():
    return CONTRACTS_PATH.read_text(encoding="utf-8")


# ── File existence ───────────────────────────────────────────────────────────


def test_output_contracts_file_exists():
    assert CONTRACTS_PATH.is_file()


# ── Contract definitions ────────────────────────────────────────────────────


def test_hidden_risk_summary_defined(contracts_text):
    assert "Hidden Risk Summary" in contracts_text


def test_complexity_heat_map_defined(contracts_text):
    assert "Complexity Heat Map" in contracts_text


def test_decision_brief_defined(contracts_text):
    assert "Decision Brief" in contracts_text


def test_pattern_remix_draft_defined(contracts_text):
    assert "Pattern Remix Draft" in contracts_text


def test_context_packet_defined(contracts_text):
    assert "Context Packet" in contracts_text


# ── Required fields per contract ─────────────────────────────────────────────


CONTRACT_FIELDS = {
    "Hidden Risk Summary": [
        "scope",
        "risks",
        "assumptions",
        "unresolved",
        "source anchors",
    ],
    "Complexity Heat Map": [
        "complexity",
        "severity",
        "confidence",
        "source",
    ],
    "Decision Brief": [
        "decision",
        "options",
        "evidence",
        "risks",
        "unresolved",
    ],
    "Pattern Remix Draft": [
        "target",
        "prior",
        "constraints",
        "approach",
        "risks",
    ],
    "Context Packet": [
        "source",
        "findings",
        "caveats",
        "confidence",
        "anchors",
    ],
}


@pytest.mark.parametrize(
    "contract_name,expected_fields",
    CONTRACT_FIELDS.items(),
    ids=CONTRACT_FIELDS.keys(),
)
def test_each_contract_has_required_sections(contracts_text, contract_name, expected_fields):
    """Each contract should mention its expected field keywords."""
    # Find the section for this contract (case-insensitive)
    text_lower = contracts_text.lower()
    contract_start = text_lower.find(contract_name.lower())
    assert contract_start != -1, f"Contract '{contract_name}' not found"

    # Look at the text from the contract heading onward
    section_text = text_lower[contract_start:]

    missing = [field for field in expected_fields if field not in section_text]
    assert not missing, f"Contract '{contract_name}' is missing mentions of: {missing}"
