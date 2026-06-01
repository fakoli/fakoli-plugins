"""Shared fixtures and import wiring for the fakoli-style script tests.

The generator and validator live in ../scripts as PEP 723 standalone scripts.
We add that directory to sys.path so the tests can import their pure functions
directly and exercise them against tmp fixtures.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Callable

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent / "schema" / "principles.schema.json"
)
DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "principles.json"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture(scope="session")
def schema() -> dict:
    """The committed principles schema."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def good_ledger() -> dict:
    """A minimal, schema-valid ledger that passes every validator check.

    proof/ref paths are repo-relative and pointed at a tmp tree by the
    `repo_root` fixture below in tests that need real filesystem checks.
    """
    return {
        "version": "1.0.0",
        "principles": [
            {
                "id": "P1",
                "name": "Proven thing",
                "principle": "The proven rule holds.",
                "why": "Prevents the proven failure.",
                "status": "proven",
                "credibility_risk": "med",
                "proof": "tests/test_proven.py::TestThing::test_it",
                "embodied_in": [
                    {
                        "plugin": "demo",
                        "ref": "src/proven.py",
                        "mechanism": "the proven mechanism",
                    }
                ],
            },
            {
                "id": "P2",
                "name": "Asserted thing",
                "principle": "The asserted rule holds.",
                "why": "Prevents the asserted failure.",
                "status": "asserted",
                "credibility_risk": "high",
                "proof": "docs/asserted.md",
                "embodied_in": [
                    {
                        "plugin": "demo",
                        "ref": "docs/asserted.md",
                        "mechanism": "the asserted mechanism",
                    }
                ],
            },
            {
                "id": "P10",
                "name": "Aspirational thing",
                "principle": "The aspirational rule will hold.",
                "why": "Prevents the aspirational failure.",
                "status": "aspirational",
                "credibility_risk": "high",
                "open_work": "build the aspirational thing",
            },
        ],
    }


@pytest.fixture
def repo_root(tmp_path: Path, good_ledger: dict) -> Path:
    """A tmp repo root with every proof/ref path in good_ledger present."""
    (tmp_path / "tests").mkdir()
    # Write a real test file containing the class/method referenced by good_ledger
    # P1's proof pointer (tests/test_proven.py::TestThing::test_it), so the new
    # symbol-existence check passes for the baseline fixture.
    (tmp_path / "tests" / "test_proven.py").write_text(
        "class TestThing:\n    def test_it(self): pass\n", encoding="utf-8"
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "proven.py").write_text("# src\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "asserted.md").write_text("# doc\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def mutate() -> Callable[[dict, Callable[[dict], None]], dict]:
    """Return a helper that deep-copies a ledger and applies a mutation."""

    def _mutate(ledger: dict, fn: Callable[[dict], None]) -> dict:
        clone = copy.deepcopy(ledger)
        fn(clone)
        return clone

    return _mutate
