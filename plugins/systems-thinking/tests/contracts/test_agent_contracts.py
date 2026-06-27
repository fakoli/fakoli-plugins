"""Tests that agent files meet the systems-thinking spec."""

import re

import pytest

from tests.conftest import PLUGIN_ROOT, parse_frontmatter

AGENTS_DIR = PLUGIN_ROOT / "agents"

EXTRACTION_AGENTS = [
    "doc-indexer.md",
    "doc-reader.md",
    "caveat-extractor.md",
    "cost-capacity-analyst.md",
    "architecture-dependency-mapper.md",
]

SYNTHESIS_AGENTS = [
    "pattern-remix-planner.md",
    "synthesis-brief-writer.md",
]

ORCHESTRATION_AGENTS = [
    "web-researcher.md",
    "extraction-planner.md",
]

ALL_AGENTS = EXTRACTION_AGENTS + SYNTHESIS_AGENTS + ORCHESTRATION_AGENTS

VALID_TOOLS = {
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "Bash",
    "Agent",
    "WebSearch",
    "WebFetch",
}


def _agent_path(name):
    return AGENTS_DIR / name


def _read_body(filename):
    _, body = parse_frontmatter(_agent_path(filename))
    return body


# ── Extraction vs. Synthesis separation ──────────────────────────────────────


@pytest.mark.parametrize("filename", EXTRACTION_AGENTS)
def test_extraction_agents_mention_no_recommendations(filename):
    """Extraction agents should signal that they do not make recommendations."""
    body = _read_body(filename).lower()
    patterns = [
        ("do not" in body and "recommend" in body),
        ("extract" in body and "not" in body and "synthesize" in body),
        "do not over-interpret" in body,
        ("avoid" in body and "recommendation" in body),
    ]
    assert any(patterns), (
        f"{filename} should mention not making recommendations or not over-interpreting"
    )


@pytest.mark.parametrize("filename", SYNTHESIS_AGENTS)
def test_synthesis_agents_mention_uncertainty(filename):
    """Synthesis agents should acknowledge uncertainty explicitly."""
    body = _read_body(filename).lower()
    keywords = ["assumption", "uncertainty", "unresolved", "unknown"]
    found = [kw for kw in keywords if kw in body]
    assert found, f"{filename} should mention at least one of: {keywords}"


# ── Source anchors ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("filename", ALL_AGENTS)
def test_agents_mention_source_anchors(filename):
    """Every agent must reference source anchors."""
    body = _read_body(filename).lower()
    assert "source" in body, f"{filename} does not mention 'source'"
    assert any(word in body for word in ("anchor", "reference", "citation")), (
        f"{filename} does not mention anchor/reference/citation"
    )


# ── Structured output ───────────────────────────────────────────────────────


@pytest.mark.parametrize("filename", ALL_AGENTS)
def test_agents_have_structured_output_section(filename):
    """Every agent should have an output-related heading."""
    body = _read_body(filename)
    pattern = re.compile(r"^#{2,3}\s+[Oo]utputs?", re.MULTILINE)
    assert pattern.search(body), f"{filename} is missing an ## Output or ### Output(s) section"


# ── Extraction behavior ─────────────────────────────────────────────────────


@pytest.mark.parametrize("filename", EXTRACTION_AGENTS)
def test_extraction_agents_have_extraction_instructions(filename):
    """Extraction agents must contain instructions about extraction."""
    body = _read_body(filename).lower()
    assert "extract" in body, f"{filename} does not contain extraction instructions"


# ── Tool scoping ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("filename", ALL_AGENTS)
def test_allowed_tools_are_valid(filename):
    """Agent allowed_tools must only use known tool names."""
    fm, _ = parse_frontmatter(_agent_path(filename))
    tools_key = next(
        (k for k in ("allowed-tools", "allowed_tools", "tools") if k in fm),
        None,
    )
    assert tools_key is not None, f"{filename} missing 'allowed-tools', 'allowed_tools', or 'tools'"
    tools = fm.get(tools_key, [])
    invalid = [t for t in tools if t not in VALID_TOOLS]
    assert not invalid, f"{filename} has invalid tools: {invalid}. Allowed: {VALID_TOOLS}"


# ── Orchestration agent contracts ──────────────────────────────────


@pytest.mark.parametrize("filename", ORCHESTRATION_AGENTS)
def test_orchestration_agents_mention_downstream(filename):
    """Orchestration agents should reference downstream agents or workflows."""
    body = _read_body(filename).lower()
    keywords = ["downstream", "dispatch", "manifest", "plan"]
    found = [kw for kw in keywords if kw in body]
    assert found, f"{filename} should mention at least one of: {keywords}"
