#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["jsonschema>=4.0"]
# ///
"""validate.py — Govern data/principles.json and its generated projection.

This is the ledger's own principles applied to itself: invariants are proven
by an executable check here, not asserted in prose. The validator exits
non-zero with a clear message when any of these hold:

  1. Schema invalidity (draft-07, schema/principles.schema.json).
  2. Duplicate `id` across principles.
  3. A proven/asserted `proof` path (the substring before `::`) that does not
     resolve on disk; for proven, the path must also be a test file.
  4. An `embodied_in[].ref` that does not resolve on disk.
  5. A proven/asserted entry missing `embodied_in`.
  6. Staleness: regenerating docs/fakoli-style.md in memory and diffing it
     against the committed file shows a difference.

Filesystem existence is checked programmatically — jsonschema cannot see the
disk. `open_work` prose is never scanned for paths.

Invocation:
    uv run --script scripts/validate.py

Paths are resolved relative to this script, so it works regardless of CWD.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

import jsonschema

import generate

# --------------------------------------------------------------------------
# Path resolution (relative to this script, never the CWD)
# --------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _SCRIPT_DIR.parent

# scripts -> fakoli-style -> plugins -> repo root
REPO_ROOT: Path = _PLUGIN_ROOT.parent.parent

DATA_PATH: Path = _PLUGIN_ROOT / "data" / "principles.json"
SCHEMA_PATH: Path = _PLUGIN_ROOT / "schema" / "principles.schema.json"
DOC_PATH: Path = _PLUGIN_ROOT / "docs" / "fakoli-style.md"

_PROOF_REQUIRED_STATUSES = ("proven", "asserted")


class ValidationError(Exception):
    """A ledger or projection invariant was violated. Carries a clear message."""


# --------------------------------------------------------------------------
# Individual checks — each raises ValidationError with a precise message
# --------------------------------------------------------------------------


def _check_schema(ledger: object, schema: dict) -> None:
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(ledger), key=lambda e: list(e.path))
    if errors:
        first = errors[0]
        location = "/".join(str(p) for p in first.path) or "<root>"
        raise ValidationError(
            f"schema invalid at {location}: {first.message}"
        )


def _check_unique_ids(principles: list[dict]) -> None:
    seen: set[str] = set()
    duplicates: list[str] = []
    for entry in principles:
        pid = entry["id"]
        if pid in seen:
            duplicates.append(pid)
        seen.add(pid)
    if duplicates:
        joined = ", ".join(sorted(set(duplicates)))
        raise ValidationError(f"duplicate principle id(s): {joined}")


def _proof_file(proof: str) -> str:
    """The repo-relative file path portion of a proof pointer (before '::')."""
    return proof.split("::", 1)[0]


def _proof_symbols(proof: str) -> list[str]:
    """The symbol segments of a proof pointer (everything after the first '::').

    'path/to/test.py::ClassName::method_name' -> ['ClassName', 'method_name']
    'path/to/test.py' -> []
    """
    parts = proof.split("::")
    return parts[1:] if len(parts) > 1 else []


def _check_proof_symbols(pid: str, proof: str, proof_path: Path) -> None:
    """Resolve each nested Python symbol structurally, ignoring comments and strings.
    This proves pointer structure, not that the referenced test passed.

    Raises ValidationError naming the first missing symbol.
    """
    symbols = _proof_symbols(proof)
    if not symbols:
        return

    try:
        node = ast.parse(proof_path.read_text(encoding="utf-8"), filename=str(proof_path))
    except (SyntaxError, UnicodeError) as exc:
        raise ValidationError(f"{pid} proof is not valid Python: {proof_path}") from exc
    for sym in symbols:
        matches = [child for child in getattr(node, "body", [])
                   if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == sym]
        if len(matches) != 1:
            raise ValidationError(f"{pid} proof symbol '{sym}' not found unambiguously in {_proof_file(proof)}")
        node = matches[0]


def _looks_like_test_file(proof_file: str) -> bool:
    """True if the proof path is a test, by pytest's discovery conventions.

    A test lives under a `test`/`tests` directory segment, or its filename
    matches `test_*.py` / `*_test.py`. This is stricter than a bare "test"
    substring so that names like `not_relevant.py` are not misclassified.
    """
    path = Path(proof_file)
    segments = {seg.lower() for seg in path.parts[:-1]}
    if "test" in segments or "tests" in segments:
        return True
    stem = path.stem.lower()
    return stem.startswith("test_") or stem.endswith("_test")


def _confined_path(root: Path, relative: str) -> Path:
    target = (root / relative).resolve()
    if Path(relative).is_absolute() or not target.is_relative_to(root.resolve()):
        raise ValidationError(f"proof/embodiment path escapes repository: {relative}")
    return target


def resolve_repo_root(explicit: Path | None = None) -> Path:
    if explicit is not None:
        root = explicit.expanduser().resolve()
        if not root.is_dir():
            raise ValidationError(f"repository directory does not exist: {root}")
        return root
    candidates = [REPO_ROOT, Path.cwd(), *Path.cwd().parents]
    for root in candidates:
        if (root / '.claude-plugin/marketplace.json').is_file() and (root / 'plugins/fakoli-style').is_dir():
            return root.resolve()
    raise ValidationError("Select the source/evidence checkout with --repo-root; an installed cache is not a repository")


def _check_proof_and_embodiment(principles: list[dict], repo_root: Path) -> None:
    for entry in principles:
        pid = entry["id"]
        status = entry["status"]

        if status in _PROOF_REQUIRED_STATUSES:
            proof = entry.get("proof")
            if not proof:
                raise ValidationError(
                    f"{pid} ({status}) is missing required 'proof'"
                )
            if "embodied_in" not in entry or not entry["embodied_in"]:
                raise ValidationError(
                    f"{pid} ({status}) is missing required 'embodied_in'"
                )

            proof_path = _confined_path(repo_root, _proof_file(proof))
            if not proof_path.is_file():
                raise ValidationError(
                    f"{pid} proof path does not exist: {_proof_file(proof)}"
                )
            if status == "proven" and not _looks_like_test_file(_proof_file(proof)):
                raise ValidationError(
                    f"{pid} is 'proven' but its proof is not a test file: "
                    f"{_proof_file(proof)}"
                )
            # Verify every ::symbol in the proof pointer actually appears in
            # the file (P2 applied to the validator itself).
            _check_proof_symbols(pid, proof, proof_path)

        for embodiment in entry.get("embodied_in", []):
            ref = embodiment["ref"]
            if not _confined_path(repo_root, ref).exists():
                raise ValidationError(
                    f"{pid} embodied_in[].ref does not exist: {ref}"
                )


def _check_staleness(ledger: dict, doc_path: Path) -> None:
    expected = generate.render(ledger)
    committed = doc_path.read_text(encoding="utf-8") if doc_path.exists() else ""
    # Normalize both sides before comparing so cosmetic differences (CRLF,
    # trailing whitespace, extra blank lines) never produce a false stale.
    if generate.normalize_for_comparison(committed) != generate.normalize_for_comparison(expected):
        raise ValidationError(
            f"{doc_path} is stale; regenerate with: "
            "uv run --script scripts/generate.py"
        )


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------


def validate(
    *,
    data_path: Path,
    schema_path: Path,
    doc_path: Path,
    repo_root: Path,
) -> None:
    """Run every governing check. Raise ValidationError on the first failure."""
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    ledger = json.loads(data_path.read_text(encoding="utf-8"))

    # Schema first: every later check assumes the versioned-object shape.
    _check_schema(ledger, schema)

    principles = ledger["principles"]
    _check_unique_ids(principles)
    _check_proof_and_embodiment(principles, repo_root)
    _check_staleness(ledger, doc_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate ledger structure, evidence pointers and projection.")
    parser.add_argument('--repo-root', type=Path, help='Checkout containing repo-relative proof files')
    parser.add_argument('--data', type=Path, default=DATA_PATH)
    parser.add_argument('--schema', type=Path, default=SCHEMA_PATH)
    parser.add_argument('--doc', type=Path, default=DOC_PATH)
    args = parser.parse_args(argv)
    try:
        validate(
            data_path=args.data,
            schema_path=args.schema,
            doc_path=args.doc,
            repo_root=resolve_repo_root(args.repo_root),
        )
    except ValidationError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not read ledger inputs: {exc}", file=sys.stderr)
        return 1

    print("OK: ledger and generated doc are valid and in sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
