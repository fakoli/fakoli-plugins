#!/usr/bin/env python3
"""Orchestrate parallel Claude CLI workers for systems-thinking workflows.

Supports two modes:
  1. Workflow mode -- run pre-processing steps then dispatch workers.
  2. Work-plan mode -- read a pre-built work-plan.json and dispatch directly.

Usage:
    python3 utils/orchestrate.py --workflow complexity-mapper --input doc.md --output output/ --parallel 3
    python3 utils/orchestrate.py --workflow complexity-mapper --input doc.md --output output/ --parallel 3 --tmux
    python3 utils/orchestrate.py --work-plan work-plan.json --output output/
    python3 utils/orchestrate.py --work-plan work-plan.json --output output/ --tmux
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Project layout helpers
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent

# Known workflows and their default agent assignments.
WORKFLOW_AGENTS: dict[str, list[str]] = {
    "complexity-mapper": [
        "caveat-extractor",
        "cost-capacity-analyst",
        "architecture-dependency-mapper",
    ],
    "context-sharding": [
        "doc-reader",
        "caveat-extractor",
    ],
    "pattern-remix": [
        "pattern-remix-planner",
    ],
    "architecture-risk-review": [
        "architecture-dependency-mapper",
        "caveat-extractor",
        "cost-capacity-analyst",
    ],
}


# ---------------------------------------------------------------------------
# Token estimation (mirrors index_doc.py)
# ---------------------------------------------------------------------------


def _estimate_tokens(text: str) -> int:
    return round(len(text.split()) * 1.3)


# ---------------------------------------------------------------------------
# Pre-processing steps
# ---------------------------------------------------------------------------


def _run_script(script_name: str, args: list[str], label: str, verbose: bool) -> Optional[Path]:
    """Run a utils/ script and return the output path (if any).

    Returns None if the script does not exist or fails.
    """
    script_path = _SCRIPT_DIR / script_name
    if not script_path.is_file():
        if verbose:
            print(f"  [skip] {label}: {script_name} not found")
        return None

    cmd = [sys.executable, str(script_path)] + args
    if verbose:
        print(f"  [run] {label}: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [warn] {label} failed (exit {result.returncode})", file=sys.stderr)
        if verbose and result.stderr:
            for line in result.stderr.strip().splitlines():
                print(f"         {line}", file=sys.stderr)
        return None

    # Try to extract the output path from stdout (convention: last line contains path).
    for line in reversed(result.stdout.strip().splitlines()):
        candidate = line.strip()
        # Lines like "Index written to output/index.json"
        if candidate.startswith("Index written to "):
            return Path(candidate.split("Index written to ", 1)[1])
        if candidate.startswith("Output written to "):
            return Path(candidate.split("Output written to ", 1)[1])
        p = Path(candidate)
        if p.suffix in (".json", ".md") and p.parent != Path("."):
            return p

    return None


def run_preprocessing(
    input_file: Path,
    output_dir: Path,
    verbose: bool = False,
) -> dict[str, Any]:
    """Run deterministic pre-processing scripts and return metadata.

    Steps: index_doc, scan_patterns, slice_sections, estimate_tokens.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, Any] = {"input": str(input_file), "steps": {}}

    print("Pre-processing...")

    # 1. Index document.
    index_out = output_dir / "index.json"
    _run_script(
        "index_doc.py",
        [str(input_file), "-o", str(index_out)],
        "index_doc",
        verbose,
    )
    if index_out.is_file():
        meta["steps"]["index"] = str(index_out)
        meta["index"] = json.loads(index_out.read_text(encoding="utf-8"))

    # 2. Scan patterns.
    patterns_out = output_dir / "patterns.json"
    _run_script(
        "scan_patterns.py",
        [str(input_file), "-o", str(patterns_out)],
        "scan_patterns",
        verbose,
    )
    if patterns_out.is_file():
        meta["steps"]["patterns"] = str(patterns_out)

    # 3. Slice sections.
    sections_dir = output_dir / "sections"
    index_file = output_dir / "index.json"
    _run_script(
        "slice_sections.py",
        [str(input_file), "--index", str(index_file), "-o", str(sections_dir)],
        "slice_sections",
        verbose,
    )
    if sections_dir.is_dir():
        meta["steps"]["sections"] = str(sections_dir)
        meta["section_files"] = sorted(str(p) for p in sections_dir.glob("*.md"))

    # 4. Estimate tokens.
    tokens_out = output_dir / "token_estimate.json"
    _run_script(
        "estimate_tokens.py",
        [str(input_file), "-o", str(tokens_out)],
        "estimate_tokens",
        verbose,
    )
    if tokens_out.is_file():
        meta["steps"]["tokens"] = str(tokens_out)

    # Fallback: if slice_sections did not produce files, treat input as a
    # single section.
    if not meta.get("section_files"):
        meta["section_files"] = [str(input_file)]

    print(f"  Sections: {len(meta['section_files'])} files")
    return meta


# ---------------------------------------------------------------------------
# Work plan generation
# ---------------------------------------------------------------------------


def _distribute_files(
    files: list[str],
    agents: list[str],
    index_data: Optional[dict[str, Any]],
) -> list[tuple[str, list[str]]]:
    """Assign section files to agents.

    Uses flagged_sections from the index (if available) to route caveat-heavy
    sections to the caveat-extractor and pricing-heavy sections to
    cost-capacity-analyst.  Remaining sections are distributed round-robin.
    """
    assignments: dict[str, list[str]] = {a: [] for a in agents}

    # Flag-based routing (best-effort).
    flagged_files: set[str] = set()
    if index_data:
        flagged = index_data.get("flagged_sections", {})
        # Build a simple section-heading -> file mapping by checking filenames.
        for f in files:
            fname = Path(f).stem.lower()
            for flag, headings in flagged.items():
                for heading in headings:
                    heading_slug = heading.lower().replace(" ", "-").replace("#", "").strip()
                    if heading_slug and heading_slug[:12] in fname:
                        if "caveat" in flag and "caveat-extractor" in assignments:
                            assignments["caveat-extractor"].append(f)
                            flagged_files.add(f)
                        elif "pricing" in flag and "cost-capacity-analyst" in assignments:
                            assignments["cost-capacity-analyst"].append(f)
                            flagged_files.add(f)

    # Round-robin for unassigned files.
    remaining = [f for f in files if f not in flagged_files]
    for i, f in enumerate(remaining):
        agent = agents[i % len(agents)]
        assignments[agent].append(f)

    return [(a, fs) for a, fs in assignments.items() if fs]


def build_work_plan(
    workflow: str,
    input_file: Path,
    output_dir: Path,
    meta: dict[str, Any],
    model: str = "sonnet",
) -> dict[str, Any]:
    """Generate a work plan from pre-processing metadata."""
    agents = WORKFLOW_AGENTS.get(workflow, ["doc-reader"])
    section_files = meta.get("section_files", [str(input_file)])
    index_data = meta.get("index")

    assignments = _distribute_files(section_files, agents, index_data)

    findings_dir = output_dir / "findings"
    findings_dir.mkdir(parents=True, exist_ok=True)

    workers: list[dict[str, Any]] = []
    for i, (agent, files) in enumerate(assignments, 1):
        workers.append(
            {
                "id": f"worker-{i}",
                "agent": agent,
                "input_files": files,
                "output_file": str(findings_dir / f"{agent}.md"),
                "model": model,
                "priority": "high" if agent == "caveat-extractor" else "medium",
            }
        )

    plan: dict[str, Any] = {
        "workflow": workflow,
        "source": str(input_file),
        "output_dir": str(findings_dir),
        "workers": workers,
        "synthesis": {
            "agent": "synthesis-brief-writer",
            "contract": "Complexity Heat Map",
            "output_file": str(output_dir / "complexity-report.md"),
        },
    }
    return plan


# ---------------------------------------------------------------------------
# Worker dispatch -- subprocess mode (non-tmux)
# ---------------------------------------------------------------------------


def _build_worker_prompt(worker: dict[str, Any]) -> str:
    """Build a prompt for a worker using build_prompt module."""
    try:
        sys.path.insert(0, str(_SCRIPT_DIR))
        import build_prompt as bp

        agents_dir = bp._auto_detect_agents_dir()
        agent_path = agents_dir / f"{worker['agent']}.md"
        if agent_path.is_file():
            fm, body = bp._parse_agent_file(agent_path)
            agent_name = fm.get("name", worker["agent"])

            input_contents: list[tuple[str, str]] = []
            for fp_str in worker.get("input_files", []):
                fp = Path(fp_str)
                if fp.is_file():
                    input_contents.append((fp.name, fp.read_text(encoding="utf-8")))

            return bp.build_prompt(
                agent_name=agent_name,
                agent_body=body,
                input_contents=input_contents,
            )
    except Exception:
        pass

    # Fallback.
    parts = [f"You are the {worker['agent']} agent.\n"]
    for fp_str in worker.get("input_files", []):
        fp = Path(fp_str)
        if fp.is_file():
            parts.append(f"## File: {fp.name}\n{fp.read_text(encoding='utf-8')}\n")
    parts.append("Produce your findings in structured Markdown.\n")
    return "\n".join(parts)


class WorkerProcess:
    """Wrapper around a subprocess.Popen for a single worker."""

    def __init__(
        self,
        worker_id: str,
        agent: str,
        proc: subprocess.Popen[bytes],
        output_file: Path,
    ) -> None:
        self.worker_id = worker_id
        self.agent = agent
        self.proc = proc
        self.output_file = output_file
        self.status: str = "RUNNING"
        self.start_time: float = time.time()
        self.end_time: Optional[float] = None

    @property
    def elapsed(self) -> float:
        end = self.end_time if self.end_time else time.time()
        return end - self.start_time

    def poll(self) -> str:
        if self.status != "RUNNING":
            return self.status
        rc = self.proc.poll()
        if rc is not None:
            self.end_time = time.time()
            if rc == 0 and self.output_file.is_file() and self.output_file.stat().st_size > 0:
                self.status = "DONE"
            else:
                self.status = "FAILED"
        return self.status

    def check_timeout(self, timeout: int) -> bool:
        if self.status == "RUNNING" and self.elapsed > timeout:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.status = "TIMEOUT"
            self.end_time = time.time()
            return True
        return False


def dispatch_workers_subprocess(
    work_plan: dict[str, Any],
    parallel: int,
    timeout: int,
    verbose: bool,
) -> list[dict[str, Any]]:
    """Dispatch workers as subprocesses and monitor until completion."""
    workers_spec = work_plan.get("workers", [])
    if not workers_spec:
        print("No workers to dispatch.")
        return []

    active: list[WorkerProcess] = []
    pending = list(workers_spec)
    completed: list[dict[str, Any]] = []

    print(f"\nDispatching {len(pending)} workers (max parallel: {parallel})...")

    while pending or active:
        # Launch workers up to the parallel limit.
        while pending and len(active) < parallel:
            worker = pending.pop(0)
            worker_id = worker.get("id", f"worker-{len(completed) + len(active) + 1}")
            output_file = Path(worker.get("output_file", f"/tmp/stp-{worker_id}.md"))
            output_file.parent.mkdir(parents=True, exist_ok=True)

            prompt = _build_worker_prompt(worker)

            if verbose:
                print(f"\n--- Prompt for {worker_id} ---")
                print(prompt[:500] + ("..." if len(prompt) > 500 else ""))
                print("--- End prompt ---\n")

            model = worker.get("model", "sonnet")
            cmd = [
                "claude",
                "--print",
                "--dangerously-skip-permissions",
                "--model",
                model,
                "-p",
                prompt,
            ]

            try:
                out_fh = open(output_file, "w", encoding="utf-8")
                proc = subprocess.Popen(
                    cmd,
                    stdout=out_fh,
                    stderr=subprocess.STDOUT,
                )
                wp = WorkerProcess(worker_id, worker.get("agent", "?"), proc, output_file)
                # Store the file handle so we can close it later.
                wp._out_fh = out_fh  # type: ignore[attr-defined]
                active.append(wp)
                print(f"  Started {worker_id} ({worker.get('agent', '?')}) pid={proc.pid}")
            except FileNotFoundError:
                print(
                    "  Error: 'claude' CLI not found. Ensure it is on PATH.",
                    file=sys.stderr,
                )
                sys.exit(1)

        # Poll active workers.
        still_active: list[WorkerProcess] = []
        for wp in active:
            wp.poll()
            wp.check_timeout(timeout)

            if wp.status != "RUNNING":
                # Close the output file handle.
                fh = getattr(wp, "_out_fh", None)
                if fh:
                    fh.close()
                completed.append(
                    {
                        "id": wp.worker_id,
                        "agent": wp.agent,
                        "status": wp.status,
                        "elapsed_seconds": round(wp.elapsed, 2),
                        "output_file": str(wp.output_file),
                    }
                )
                print(f"  {wp.worker_id}: {wp.status} ({wp.elapsed:.1f}s)")
            else:
                still_active.append(wp)

        active = still_active

        if active:
            time.sleep(1)

    return completed


# ---------------------------------------------------------------------------
# Worker dispatch -- tmux mode
# ---------------------------------------------------------------------------


def dispatch_workers_tmux(
    work_plan: dict[str, Any],
    output_dir: Path,
    session: str,
    timeout: int,
    layout: str = "tiled",
) -> list[dict[str, Any]]:
    """Dispatch workers via tmux_runner."""
    try:
        sys.path.insert(0, str(_SCRIPT_DIR))
        import tmux_runner
    except ImportError:
        print(
            "Error: tmux_runner.py not found in utils/.",
            file=sys.stderr,
        )
        sys.exit(1)

    return tmux_runner.run_workers_in_tmux(
        session=session,
        work_plan=work_plan,
        output_dir=output_dir,
        timeout=timeout,
        layout=layout,
    )


# ---------------------------------------------------------------------------
# Post-processing: aggregation and synthesis
# ---------------------------------------------------------------------------


def run_aggregation(output_dir: Path, verbose: bool) -> None:
    """Run aggregate.py on the output directory if available."""
    _run_script(
        "aggregate.py",
        [str(output_dir)],
        "aggregate",
        verbose,
    )


def run_synthesis(
    work_plan: dict[str, Any],
    output_dir: Path,
    model: str,
    timeout: int,
    verbose: bool,
) -> Optional[dict[str, Any]]:
    """Run the synthesis step if specified in the work plan."""
    synthesis = work_plan.get("synthesis")
    if not synthesis:
        return None

    agent = synthesis.get("agent", "synthesis-brief-writer")
    contract = synthesis.get("contract", "")
    output_file = Path(synthesis.get("output_file", str(output_dir / "synthesis.md")))
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Gather all findings files as input.
    findings_dir = Path(work_plan.get("output_dir", str(output_dir / "findings")))
    input_files: list[str] = []
    if findings_dir.is_dir():
        input_files = sorted(str(p) for p in findings_dir.glob("*.md"))

    if not input_files:
        print("  [skip] synthesis: no findings files to synthesize")
        return None

    worker = {
        "id": "synthesis",
        "agent": agent,
        "input_files": input_files,
        "output_file": str(output_file),
        "model": model,
    }

    print(f"\nRunning synthesis ({agent})...")
    prompt = _build_worker_prompt(worker)

    # Add contract guidance to the prompt.
    if contract:
        prompt += f"\n\n## Output Contract: {contract}\n"
        prompt += "Follow the output contract structure defined in the project conventions.\n"

    cmd = [
        "claude",
        "--print",
        "--dangerously-skip-permissions",
        "--model",
        model,
        "-p",
        prompt,
    ]

    try:
        with open(output_file, "w", encoding="utf-8") as fh:
            result = subprocess.run(
                cmd,
                stdout=fh,
                stderr=subprocess.PIPE,
                timeout=timeout,
                text=True,
            )
    except subprocess.TimeoutExpired:
        print("  Synthesis: TIMEOUT")
        return {"id": "synthesis", "status": "TIMEOUT", "output_file": str(output_file)}
    except FileNotFoundError:
        print("  Error: 'claude' CLI not found.", file=sys.stderr)
        return None

    status = "DONE" if result.returncode == 0 else "FAILED"
    print(f"  Synthesis: {status}")
    return {
        "id": "synthesis",
        "agent": agent,
        "status": status,
        "output_file": str(output_file),
    }


# ---------------------------------------------------------------------------
# Run summary
# ---------------------------------------------------------------------------


def write_run_summary(
    output_dir: Path,
    work_plan: dict[str, Any],
    worker_results: list[dict[str, Any]],
    synthesis_result: Optional[dict[str, Any]],
    total_elapsed: float,
) -> Path:
    """Write a run summary JSON file."""
    summary = {
        "workflow": work_plan.get("workflow", "unknown"),
        "source": work_plan.get("source", "unknown"),
        "total_elapsed_seconds": round(total_elapsed, 2),
        "worker_count": len(worker_results),
        "workers": worker_results,
        "synthesis": synthesis_result,
        "output_dir": str(output_dir),
    }
    summary_path = output_dir / "run-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary_path


def print_summary_table(
    worker_results: list[dict[str, Any]],
    synthesis_result: Optional[dict[str, Any]],
) -> None:
    """Print a formatted summary table."""
    print(f"\n{'=' * 60}")
    print(f"{'ID':<20} {'Agent':<28} {'Status':<10} {'Time':>8}")
    print(f"{'-' * 20} {'-' * 28} {'-' * 10} {'-' * 8}")
    for r in worker_results:
        elapsed = r.get("elapsed_seconds", 0)
        print(
            f"{r.get('id', '?'):<20} "
            f"{r.get('agent', '?'):<28} "
            f"{r.get('status', '?'):<10} "
            f"{elapsed:>7.1f}s"
        )
    if synthesis_result:
        print(
            f"{'synthesis':<20} "
            f"{synthesis_result.get('agent', '?'):<28} "
            f"{synthesis_result.get('status', '?'):<10} "
            f"{'':>8}"
        )
    print(f"{'=' * 60}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Orchestrate parallel Claude CLI workers for systems-thinking workflows."
        ),
    )

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--workflow",
        choices=list(WORKFLOW_AGENTS.keys()),
        help="Named workflow to run (complexity-mapper, context-sharding, "
        "pattern-remix, architecture-risk-review)",
    )
    mode_group.add_argument(
        "--work-plan",
        type=Path,
        help="Path to a pre-built work plan JSON file",
    )

    parser.add_argument(
        "--input",
        type=Path,
        help="Input file or directory (required for --workflow mode)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output directory for all results",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=3,
        help="Maximum number of parallel workers (default: 3)",
    )
    parser.add_argument(
        "--tmux",
        action="store_true",
        help="Use tmux for worker management (visible panes)",
    )
    parser.add_argument(
        "--tmux-session",
        default="stp-workers",
        help="Tmux session name (default: stp-workers)",
    )
    parser.add_argument(
        "--model",
        default="sonnet",
        help="Model for workers (default: sonnet)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Per-worker timeout in seconds (default: 120)",
    )
    parser.add_argument(
        "--skip-preprocess",
        action="store_true",
        help="Skip deterministic pre-processing, go straight to dispatch",
    )
    parser.add_argument(
        "--skip-synthesis",
        action="store_true",
        help="Skip the synthesis step, just aggregate",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the work plan without executing",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print worker prompts and detailed status",
    )
    args = parser.parse_args()

    start_time = time.time()
    args.output.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------------
    # Determine the work plan.
    # -----------------------------------------------------------------------
    if args.work_plan:
        # Mode 2: pre-built work plan.
        if not args.work_plan.is_file():
            print(f"Error: work plan not found: {args.work_plan}", file=sys.stderr)
            sys.exit(1)
        work_plan = json.loads(args.work_plan.read_text(encoding="utf-8"))
        print(f"Loaded work plan: {args.work_plan}")
    else:
        # Mode 1: workflow mode -- need --input.
        if not args.input:
            print("Error: --input is required when using --workflow.", file=sys.stderr)
            sys.exit(1)
        if not args.input.exists():
            print(f"Error: input not found: {args.input}", file=sys.stderr)
            sys.exit(1)

        # Pre-processing.
        if args.skip_preprocess:
            meta: dict[str, Any] = {
                "input": str(args.input),
                "section_files": [str(args.input)],
            }
        else:
            meta = run_preprocessing(args.input, args.output, args.verbose)

        # Build the work plan.
        work_plan = build_work_plan(
            workflow=args.workflow,  # type: ignore[arg-type]
            input_file=args.input,
            output_dir=args.output,
            meta=meta,
            model=args.model,
        )

    # Override model in all workers if specified via CLI.
    for w in work_plan.get("workers", []):
        if args.model:
            w["model"] = args.model

    # -----------------------------------------------------------------------
    # Dry run: print and exit.
    # -----------------------------------------------------------------------
    if args.dry_run:
        print("\n--- Work Plan (dry run) ---")
        print(json.dumps(work_plan, indent=2))
        # Also write it to disk for later use.
        plan_path = args.output / "work-plan.json"
        plan_path.write_text(json.dumps(work_plan, indent=2) + "\n", encoding="utf-8")
        print(f"\nWork plan written to {plan_path}")
        sys.exit(0)

    # Save the work plan for reference.
    plan_path = args.output / "work-plan.json"
    plan_path.write_text(json.dumps(work_plan, indent=2) + "\n", encoding="utf-8")

    # -----------------------------------------------------------------------
    # Dispatch workers.
    # -----------------------------------------------------------------------
    if args.tmux:
        worker_results = dispatch_workers_tmux(
            work_plan=work_plan,
            output_dir=args.output,
            session=args.tmux_session,
            timeout=args.timeout,
        )
    else:
        worker_results = dispatch_workers_subprocess(
            work_plan=work_plan,
            parallel=args.parallel,
            timeout=args.timeout,
            verbose=args.verbose,
        )

    # -----------------------------------------------------------------------
    # Post-processing.
    # -----------------------------------------------------------------------
    run_aggregation(args.output, args.verbose)

    synthesis_result: Optional[dict[str, Any]] = None
    if not args.skip_synthesis:
        synthesis_result = run_synthesis(
            work_plan=work_plan,
            output_dir=args.output,
            model=args.model,
            timeout=args.timeout,
            verbose=args.verbose,
        )

    # -----------------------------------------------------------------------
    # Summary.
    # -----------------------------------------------------------------------
    total_elapsed = time.time() - start_time
    print_summary_table(worker_results, synthesis_result)

    summary_path = write_run_summary(
        output_dir=args.output,
        work_plan=work_plan,
        worker_results=worker_results,
        synthesis_result=synthesis_result,
        total_elapsed=total_elapsed,
    )
    print(f"\nRun summary: {summary_path}")
    print(f"Total time: {total_elapsed:.1f}s")


if __name__ == "__main__":
    main()
