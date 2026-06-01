"""Tests for the governing validator (scripts/validate.py).

Each failure mode is exercised in isolation against a tmp repo root so the
filesystem checks have a real tree to resolve against. A passing baseline
(the good_ledger + its freshly generated doc) anchors the suite.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import generate
import validate


def _write(path: Path, ledger: dict) -> Path:
    path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    return path


def _validate(
    tmp_path: Path,
    repo_root: Path,
    schema: dict,
    ledger: dict,
    doc_text: str | None = None,
) -> None:
    """Wire a full validation run against tmp fixtures.

    When doc_text is None the doc is generated from the ledger, so a passing
    ledger produces a non-stale doc by construction.
    """
    data_path = _write(tmp_path / "principles.json", ledger)
    schema_path = tmp_path / "principles.schema.json"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    doc_path = tmp_path / "fakoli-style.md"
    if doc_text is None:
        # Render the projection from the ledger so a passing ledger yields a
        # non-stale doc. An invalid ledger may not be renderable; in that case
        # leave the doc empty and let validate.validate surface the real fault.
        try:
            doc_text = generate.render(ledger)
        except (KeyError, TypeError):
            doc_text = ""
    doc_path.write_text(doc_text, encoding="utf-8")

    validate.validate(
        data_path=data_path,
        schema_path=schema_path,
        doc_path=doc_path,
        repo_root=repo_root,
    )


# --------------------------------------------------------------------------
# Passing baseline
# --------------------------------------------------------------------------


def test_good_ledger_passes(
    tmp_path: Path, repo_root: Path, schema: dict, good_ledger: dict
) -> None:
    # Should not raise.
    _validate(tmp_path, repo_root, schema, good_ledger)


def test_committed_seed_and_doc_pass() -> None:
    """validate.py exits 0 against the committed seed data and generated doc."""
    validate.validate(
        data_path=Path(validate.DATA_PATH),
        schema_path=Path(validate.SCHEMA_PATH),
        doc_path=Path(validate.DOC_PATH),
        repo_root=Path(validate.REPO_ROOT),
    )


# --------------------------------------------------------------------------
# Failure mode: schema invalidity
# --------------------------------------------------------------------------


def test_schema_invalid_bad_status(
    tmp_path: Path, repo_root: Path, schema: dict, good_ledger: dict, mutate
) -> None:
    bad = mutate(good_ledger, lambda d: d["principles"][0].__setitem__("status", "nope"))

    with pytest.raises(validate.ValidationError, match="schema"):
        _validate(tmp_path, repo_root, schema, bad)


def test_schema_invalid_bare_array_not_object(
    tmp_path: Path, repo_root: Path, schema: dict, good_ledger: dict
) -> None:
    bare = good_ledger["principles"]  # the array, not the versioned object

    with pytest.raises(validate.ValidationError, match="schema"):
        _validate(tmp_path, repo_root, schema, bare)


# --------------------------------------------------------------------------
# Failure mode: nonexistent proof path
# --------------------------------------------------------------------------


def test_proof_path_does_not_exist(
    tmp_path: Path, repo_root: Path, schema: dict, good_ledger: dict, mutate
) -> None:
    bad = mutate(
        good_ledger,
        lambda d: d["principles"][0].__setitem__(
            "proof", "tests/does_not_exist.py::T::t"
        ),
    )

    with pytest.raises(validate.ValidationError, match="proof"):
        _validate(tmp_path, repo_root, schema, bad)


def test_proof_resolution_strips_double_colon_suffix(
    tmp_path: Path, repo_root: Path, schema: dict, good_ledger: dict
) -> None:
    """Only the substring before :: is checked on the filesystem."""
    # good_ledger P1 proof is tests/test_proven.py::TestThing::test_it and the
    # file tests/test_proven.py exists in repo_root, so this must pass.
    _validate(tmp_path, repo_root, schema, good_ledger)


def test_proven_proof_must_be_a_test_file(
    tmp_path: Path, repo_root: Path, schema: dict, good_ledger: dict, mutate
) -> None:
    """A proven entry whose proof path resolves but isn't a test file fails."""
    (repo_root / "src" / "module.py").write_text("# x\n", encoding="utf-8")
    bad = mutate(
        good_ledger,
        lambda d: d["principles"][0].__setitem__("proof", "src/module.py"),
    )

    with pytest.raises(validate.ValidationError, match="test"):
        _validate(tmp_path, repo_root, schema, bad)


# --------------------------------------------------------------------------
# Failure mode: nonexistent embodied_in[].ref
# --------------------------------------------------------------------------


def test_embodied_in_ref_does_not_exist(
    tmp_path: Path, repo_root: Path, schema: dict, good_ledger: dict, mutate
) -> None:
    bad = mutate(
        good_ledger,
        lambda d: d["principles"][0]["embodied_in"][0].__setitem__(
            "ref", "src/ghost.py"
        ),
    )

    with pytest.raises(validate.ValidationError, match="ref"):
        _validate(tmp_path, repo_root, schema, bad)


# --------------------------------------------------------------------------
# Failure mode: missing embodied_in on proven/asserted
#
# The schema already requires embodied_in for proven/asserted, so removing it
# trips the schema check. The validator must still reject it (clear message).
# --------------------------------------------------------------------------


def test_proven_missing_embodied_in(
    tmp_path: Path, repo_root: Path, schema: dict, good_ledger: dict, mutate
) -> None:
    bad = mutate(good_ledger, lambda d: d["principles"][0].pop("embodied_in"))

    with pytest.raises(validate.ValidationError):
        _validate(tmp_path, repo_root, schema, bad)


def test_open_work_prose_is_never_scanned_for_paths(
    tmp_path: Path, repo_root: Path, schema: dict, good_ledger: dict, mutate
) -> None:
    """An aspirational open_work mentioning a fake path must not fail."""
    bad = mutate(
        good_ledger,
        lambda d: d["principles"][2].__setitem__(
            "open_work", "see src/totally/fake/path.py for the plan"
        ),
    )

    # No raise: open_work is prose, not a checked path.
    _validate(tmp_path, repo_root, schema, bad)


# --------------------------------------------------------------------------
# Failure mode: duplicate ids
# --------------------------------------------------------------------------


def test_duplicate_ids_rejected(
    tmp_path: Path, repo_root: Path, schema: dict, good_ledger: dict, mutate
) -> None:
    bad = mutate(good_ledger, lambda d: d["principles"][1].__setitem__("id", "P1"))

    with pytest.raises(validate.ValidationError, match="(?i)duplicate"):
        _validate(tmp_path, repo_root, schema, bad)


# --------------------------------------------------------------------------
# Failure mode: staleness
# --------------------------------------------------------------------------


def test_stale_doc_rejected(
    tmp_path: Path, repo_root: Path, schema: dict, good_ledger: dict
) -> None:
    stale = generate.render(good_ledger) + "\nhand-edited tail\n"

    with pytest.raises(validate.ValidationError, match="(?i)stale|regenerat"):
        _validate(tmp_path, repo_root, schema, good_ledger, doc_text=stale)


# --------------------------------------------------------------------------
# Fix 1: CRLF / trailing-whitespace normalization in staleness check
# --------------------------------------------------------------------------


def test_staleness_crlf_does_not_false_positive(
    tmp_path: Path, repo_root: Path, schema: dict, good_ledger: dict
) -> None:
    """Identical content with CRLF line endings must pass the staleness check."""
    canonical = generate.render(good_ledger)
    crlf_version = canonical.replace("\n", "\r\n")

    # Must NOT raise — only line endings differ, not content.
    _validate(tmp_path, repo_root, schema, good_ledger, doc_text=crlf_version)


def test_staleness_trailing_whitespace_does_not_false_positive(
    tmp_path: Path, repo_root: Path, schema: dict, good_ledger: dict
) -> None:
    """Lines with trailing spaces or blank lines with spaces must pass."""
    canonical = generate.render(good_ledger)
    # Add trailing spaces to every line and extra blank lines at the end.
    padded = "\n".join(line + "   " for line in canonical.splitlines()) + "\n\n\n"

    _validate(tmp_path, repo_root, schema, good_ledger, doc_text=padded)


def test_staleness_real_content_change_still_fails(
    tmp_path: Path, repo_root: Path, schema: dict, good_ledger: dict
) -> None:
    """A genuine content difference must still be caught."""
    stale = generate.render(good_ledger).replace("Proven thing", "Changed name", 1)

    with pytest.raises(validate.ValidationError, match="(?i)stale|regenerat"):
        _validate(tmp_path, repo_root, schema, good_ledger, doc_text=stale)


# --------------------------------------------------------------------------
# Fix 2: Verify ::symbol names exist in the proof file
# --------------------------------------------------------------------------


def test_proof_symbol_missing_class_fails(
    tmp_path: Path, repo_root: Path, schema: dict, good_ledger: dict, mutate
) -> None:
    """A proof pointer referencing a nonexistent class must fail."""
    # test_proven.py exists in repo_root but contains only '# test\n'
    bad = mutate(
        good_ledger,
        lambda d: d["principles"][0].__setitem__(
            "proof", "tests/test_proven.py::MissingClass::test_it"
        ),
    )

    with pytest.raises(validate.ValidationError, match="(?i)symbol|MissingClass"):
        _validate(tmp_path, repo_root, schema, bad)


def test_proof_symbol_missing_method_fails(
    tmp_path: Path, repo_root: Path, schema: dict, good_ledger: dict, mutate
) -> None:
    """A proof pointer with a real class but a renamed method must fail."""
    (repo_root / "tests" / "test_proven.py").write_text(
        "class TestThing:\n    def test_it(self): pass\n", encoding="utf-8"
    )
    bad = mutate(
        good_ledger,
        lambda d: d["principles"][0].__setitem__(
            "proof", "tests/test_proven.py::TestThing::renamed_method"
        ),
    )

    with pytest.raises(validate.ValidationError, match="(?i)symbol|renamed_method"):
        _validate(tmp_path, repo_root, schema, bad)


def test_proof_symbol_both_present_passes(
    tmp_path: Path, repo_root: Path, schema: dict, good_ledger: dict, mutate
) -> None:
    """A proof pointer with class and method both present in the file must pass."""
    (repo_root / "tests" / "test_proven.py").write_text(
        "class TestThing:\n    def test_it(self): pass\n", encoding="utf-8"
    )
    # good_ledger P1 proof is tests/test_proven.py::TestThing::test_it
    _validate(tmp_path, repo_root, schema, good_ledger)


def test_committed_p1_proof_symbols_pass() -> None:
    """The committed P1 proof (TestEvidenceGateDelegation::...) must pass.

    Both the class and the method exist in the real test file on disk.
    """
    validate.validate(
        data_path=Path(validate.DATA_PATH),
        schema_path=Path(validate.SCHEMA_PATH),
        doc_path=Path(validate.DOC_PATH),
        repo_root=Path(validate.REPO_ROOT),
    )


# --------------------------------------------------------------------------
# Fix 3: Direct test of the embodiment guard (bypassing schema)
# --------------------------------------------------------------------------


def test_embodiment_guard_raises_without_schema(repo_root: Path) -> None:
    """_check_proof_and_embodiment raises with 'embodied_in' in its message
    when called directly on a proven entry missing embodied_in, even if the
    schema check was never run."""
    principles = [
        {
            "id": "P1",
            "name": "Proven thing",
            "principle": "The proven rule holds.",
            "why": "Prevents the proven failure.",
            "status": "proven",
            "credibility_risk": "med",
            "proof": "tests/test_proven.py::TestThing::test_it",
            # embodied_in intentionally absent
        }
    ]
    # Write the proof file so the path check passes.
    (repo_root / "tests" / "test_proven.py").write_text(
        "class TestThing:\n    def test_it(self): pass\n", encoding="utf-8"
    )

    with pytest.raises(validate.ValidationError, match="embodied_in"):
        validate._check_proof_and_embodiment(principles, repo_root)


# --------------------------------------------------------------------------
# Fix 4: lstrip("P") → id[1:] for P10 ordering
# --------------------------------------------------------------------------


def test_numeric_id_p10_sorts_after_p2() -> None:
    """P10 must sort after P2 when risk and status are equal (numeric ordering)."""
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


def test_numeric_id_pppp10_not_misread() -> None:
    """lstrip('P') would parse 'PPP10' as 10, but id[1:] makes it 'PP10' -> ValueError.

    Since the schema constrains ids to ^P[0-9]+$, this is a regression guard:
    confirm _numeric_id raises for a malformed id rather than silently stripping.
    """
    entry = {"id": "PP10"}
    with pytest.raises(ValueError):
        generate._numeric_id(entry)
