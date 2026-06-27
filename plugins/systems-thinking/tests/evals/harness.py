#!/usr/bin/env python3
"""
Eval harness for systems-thinking.

Usage:
    python harness.py                          # run all evals
    python harness.py cases/complexity_mapper_basic.yaml  # run one eval
    python harness.py --dry-run               # validate cases without running
    python harness.py --output-dir results/   # save results as JSON
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from graders.composite import grade_composite
from graders.cross_reference_consistency import grade_cross_reference_consistency
from graders.evidence_labels import grade_evidence_labels
from graders.file_exists import grade_files_exist
from graders.forbidden_check import (
    grade_no_forbidden_files,
    grade_no_forbidden_patterns,
)
from graders.quantitative_claims import grade_quantitative_claims
from graders.schema_match import grade_markdown_structure
from graders.section_check import grade_sections
from graders.source_anchor_coverage import grade_source_anchor_coverage

HARNESS_DIR = Path(__file__).resolve().parent
CASES_DIR = HARNESS_DIR / "cases"
FIXTURES_DIR = HARNESS_DIR / "fixtures"
PROJECT_ROOT = HARNESS_DIR.parent.parent


def load_case(case_path: Path) -> dict:
    """Load and validate an eval case YAML file.

    Args:
        case_path: Absolute or relative path to the YAML case file.

    Returns:
        Parsed case dict.

    Raises:
        ValueError: If the case is missing required fields.
    """
    with open(case_path, "r", encoding="utf-8") as fh:
        case = yaml.safe_load(fh)

    required_fields = ["name", "description", "prompt", "expected_outcomes"]
    missing = [f for f in required_fields if f not in case]
    if missing:
        raise ValueError(f"Case {case_path.name} missing required fields: {missing}")

    return case


def discover_cases(target: str | None = None) -> list[Path]:
    """Discover eval case YAML files.

    Args:
        target: Optional path to a single case file. If None, discovers
                all .yaml files in the cases/ directory.

    Returns:
        Sorted list of case file paths.
    """
    if target:
        target_path = Path(target)
        if not target_path.is_absolute():
            target_path = HARNESS_DIR / target_path
        if not target_path.exists():
            raise FileNotFoundError(f"Case file not found: {target_path}")
        return [target_path]

    cases = sorted(CASES_DIR.glob("*.yaml"))
    if not cases:
        raise FileNotFoundError(f"No .yaml case files found in {CASES_DIR}")
    return cases


def run_setup(case: dict, workdir: Path) -> None:
    """Execute setup steps for an eval case.

    Supports the following step types:
        - copy_fixture: Copy a fixture file into the working directory.

    Args:
        case: The parsed eval case dict.
        workdir: The temporary working directory for this eval run.
    """
    for step in case.get("setup", []):
        if "copy_fixture" in step:
            src = HARNESS_DIR / step["copy_fixture"]
            dest = workdir / step["to"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)


def run_claude(prompt: str, workdir: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    """Invoke the Claude CLI with the given prompt.

    Args:
        prompt: The prompt text to send to Claude.
        workdir: Working directory for the subprocess.
        timeout: Timeout in seconds.

    Returns:
        The completed process result.

    Raises:
        subprocess.TimeoutExpired: If the command exceeds the timeout.
    """
    return subprocess.run(
        ["claude", "--print", "--dangerously-skip-permissions", "-p", prompt],
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _write_stdout_file(workdir: Path, stdout: str) -> None:
    """Write captured stdout to a _stdout file in the workdir for grading."""
    stdout_path = workdir / "_stdout"
    stdout_path.write_text(stdout, encoding="utf-8")


def run_graders(case: dict, workdir: Path) -> list[dict]:
    """Run all graders defined in the case against the working directory.

    Args:
        case: The parsed eval case dict.
        workdir: The working directory containing outputs.

    Returns:
        List of grader result dicts.
    """
    results: list[dict] = []

    for outcome in case.get("expected_outcomes", []):
        result = _run_single_grader(outcome, workdir, expected=True)
        results.append(result)

    for outcome in case.get("forbidden_outcomes", []):
        result = _run_single_grader(outcome, workdir, expected=False)
        results.append(result)

    return results


def _run_single_grader(outcome: dict, workdir: Path, expected: bool) -> dict:
    """Run a single grader based on the outcome definition.

    Args:
        outcome: An outcome dict from the case definition.
        workdir: The working directory.
        expected: If True, this is an expected outcome (things should pass).
                  If False, this is a forbidden outcome (things should fail).

    Returns:
        Grader result dict.
    """
    outcome_type = outcome["type"]

    if outcome_type == "file_exists":
        result = grade_files_exist(workdir, outcome["files"])
        if not expected:
            # Invert: for forbidden outcomes, files should NOT exist
            result = grade_no_forbidden_files(workdir, outcome["files"])
        return result

    if outcome_type == "section_check":
        filepath = _resolve_file(outcome["file"], workdir)
        return grade_sections(filepath, outcome["sections"])

    if outcome_type == "forbidden_patterns":
        filepath = _resolve_file(outcome["file"], workdir)
        return grade_no_forbidden_patterns(filepath, outcome["patterns"])

    if outcome_type == "markdown_structure":
        filepath = _resolve_file(outcome["file"], workdir)
        return grade_markdown_structure(filepath, outcome["headings"])

    if outcome_type == "source_anchor_coverage":
        filepath = _resolve_file(outcome["file"], workdir)
        config = {"min_coverage": outcome.get("min_coverage", 0.5)}
        return grade_source_anchor_coverage(filepath, config)

    if outcome_type == "evidence_labels":
        filepath = _resolve_file(outcome["file"], workdir)
        config = {
            "min_source_labels": outcome.get("min_source_labels", 3),
            "min_inferred_labels": outcome.get("min_inferred_labels", 1),
        }
        return grade_evidence_labels(filepath, config)

    if outcome_type == "quantitative_claims":
        filepath = _resolve_file(outcome["file"], workdir)
        config = {"claims": outcome.get("claims", [])}
        return grade_quantitative_claims(filepath, config)

    if outcome_type == "cross_reference_consistency":
        filepath = _resolve_file(outcome["file"], workdir)
        config = {
            "sections_to_cross_check": outcome.get("sections_to_cross_check", []),
            "min_overlap": outcome.get("min_overlap", 0.3),
        }
        return grade_cross_reference_consistency(filepath, config)

    return {
        "pass": False,
        "score": 0.0,
        "error": f"Unknown outcome type: {outcome_type}",
    }


def _resolve_file(file_ref: str, workdir: Path) -> Path:
    """Resolve a file reference from a case definition.

    The special value ``_stdout`` refers to the captured stdout file.

    Args:
        file_ref: Relative path or ``_stdout``.
        workdir: The working directory.

    Returns:
        Resolved absolute path.
    """
    return workdir / file_ref


def run_single_eval(case_path: Path, dry_run: bool = False) -> dict[str, Any]:
    """Run a single eval case.

    Args:
        case_path: Path to the YAML case file.
        dry_run: If True, validate the case without executing.

    Returns:
        Result dict with keys: name, path, pass, score, duration, error, grader_results.
    """
    result: dict[str, Any] = {
        "name": "",
        "path": str(case_path),
        "pass": False,
        "score": 0.0,
        "duration": 0.0,
        "error": None,
        "grader_results": [],
        "stdout_length": 0,
        "output_file_sizes": {},
        "timed_out": False,
    }

    try:
        case = load_case(case_path)
    except (ValueError, yaml.YAMLError) as exc:
        result["error"] = f"Failed to load case: {exc}"
        return result

    result["name"] = case["name"]

    if dry_run:
        result["pass"] = True
        result["score"] = 1.0
        result["error"] = "(dry-run: case validated successfully)"
        return result

    workdir = Path(tempfile.mkdtemp(prefix=f"eval_{case['name']}_"))

    try:
        run_setup(case, workdir)

        start_time = time.monotonic()
        timeout = case.get("timeout", 120)

        try:
            proc = run_claude(case["prompt"], workdir, timeout)
        except subprocess.TimeoutExpired:
            result["error"] = f"Claude CLI timed out after {timeout}s"
            result["duration"] = timeout
            result["timed_out"] = True
            return result
        except FileNotFoundError:
            result["error"] = "Claude CLI not found; ensure 'claude' is on PATH"
            return result

        result["duration"] = time.monotonic() - start_time

        # Write stdout for graders that reference _stdout
        stdout_text = proc.stdout or ""
        _write_stdout_file(workdir, stdout_text)
        result["stdout_length"] = len(stdout_text)

        # Collect output file sizes
        output_dir = workdir / "output"
        if output_dir.exists():
            for f in output_dir.rglob("*"):
                if f.is_file():
                    result["output_file_sizes"][str(f.relative_to(workdir))] = f.stat().st_size

        if proc.returncode != 0 and proc.stderr:
            result["error"] = f"Claude CLI exited with code {proc.returncode}: {proc.stderr[:500]}"

        grader_results = run_graders(case, workdir)
        result["grader_results"] = grader_results

        composite = grade_composite(grader_results)
        result["pass"] = composite["pass"]
        result["score"] = composite["score"]

    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    return result


def print_summary(results: list[dict[str, Any]]) -> None:
    """Print a summary table of eval results to stdout.

    Args:
        results: List of per-case result dicts.
    """
    name_width = max(len(r["name"]) for r in results) if results else 20
    name_width = max(name_width, 20)

    header = f"{'NAME':<{name_width}}  {'PASS':>6}  {'SCORE':>6}  {'TIME':>8}  NOTES"
    print()
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    for r in results:
        status = "PASS" if r["pass"] else "FAIL"
        score_str = f"{r['score']:.2f}"
        time_str = f"{r['duration']:.1f}s"
        notes = r.get("error", "") or ""

        # Summarize failures
        if not r["pass"] and not notes:
            failed_count = sum(1 for gr in r.get("grader_results", []) if not gr.get("pass", False))
            total_count = len(r.get("grader_results", []))
            notes = f"{failed_count}/{total_count} checks failed"

        print(f"{r['name']:<{name_width}}  {status:>6}  {score_str:>6}  {time_str:>8}  {notes}")

    print("=" * len(header))

    passed = sum(1 for r in results if r["pass"])
    total = len(results)
    print(f"\nTotal: {passed}/{total} passed")
    print()


def save_results(results: list[dict[str, Any]], output_dir: Path) -> Path:
    """Save eval results as a JSON file.

    Args:
        results: List of per-case result dicts.
        output_dir: Directory to write the results file into.

    Returns:
        Path to the written JSON file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"eval_results_{timestamp}.json"

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "timestamp": timestamp,
                "total": len(results),
                "passed": sum(1 for r in results if r["pass"]),
                "results": results,
            },
            fh,
            indent=2,
            default=str,
        )

    return output_path


def main() -> int:
    """Entry point for the eval harness CLI.

    Returns:
        Exit code: 0 if all evals pass, 1 otherwise.
    """
    parser = argparse.ArgumentParser(
        description="Eval harness for systems-thinking",
    )
    parser.add_argument(
        "case",
        nargs="?",
        default=None,
        help="Path to a specific case YAML file (default: run all cases)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate case files without executing prompts",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory to save results as JSON",
    )
    args = parser.parse_args()

    try:
        case_paths = discover_cases(args.case)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Discovered {len(case_paths)} eval case(s)")
    if args.dry_run:
        print("Mode: dry-run (validating cases only)")

    results: list[dict[str, Any]] = []
    for case_path in case_paths:
        print(f"  Running: {case_path.name} ...", end="", flush=True)
        result = run_single_eval(case_path, dry_run=args.dry_run)
        status = "PASS" if result["pass"] else "FAIL"
        print(f" {status}")
        results.append(result)

    print_summary(results)

    if args.output_dir:
        output_path = save_results(results, Path(args.output_dir))
        print(f"Results saved to: {output_path}")

    all_passed = all(r["pass"] for r in results)
    return 0 if all_passed else 1


if __name__ == "__main__":
    # Ensure the project root is on the Python path so grader imports resolve.
    sys.path.insert(0, str(PROJECT_ROOT))
    sys.exit(main())
