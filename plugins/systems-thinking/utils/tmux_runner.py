#!/usr/bin/env python3
"""Manage Claude CLI workers inside tmux sessions.

Typically called by orchestrate.py, but can be invoked directly.

Usage:
    python3 utils/tmux_runner.py --session stp-workers --workers work-plan.json --output output/
    python3 utils/tmux_runner.py --session stp-workers --workers work-plan.json --output output/ --cleanup
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WORKER_DONE_SENTINEL = "WORKER_DONE"
DEFAULT_TIMEOUT = 120
POLL_INTERVAL = 2  # seconds between status checks


# ---------------------------------------------------------------------------
# tmux helpers
# ---------------------------------------------------------------------------


def _run_tmux(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a tmux command and return the result."""
    cmd = ["tmux"] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def _tmux_session_exists(session: str) -> bool:
    result = _run_tmux("has-session", "-t", session, check=False)
    return result.returncode == 0


def _create_session(session: str) -> None:
    """Create a new detached tmux session."""
    _run_tmux("new-session", "-d", "-s", session, "-x", "200", "-y", "50")


def _create_pane(session: str, pane_name: str, layout: str, first: bool) -> str:
    """Create a pane in the session and return its target identifier.

    For the first worker we reuse the initial pane; for subsequent workers we
    split according to the requested layout.
    """
    if first:
        # Rename the initial window/pane.
        target = f"{session}:0"
        _run_tmux("rename-window", "-t", target, pane_name)
        return f"{session}:0.0"

    split_flag = "-v"  # vertical split (stacked)
    if layout == "horizontal":
        split_flag = "-h"

    _run_tmux("split-window", split_flag, "-t", f"{session}:0")

    # After splitting, select the tiled layout for even sizing when there are
    # many panes.
    if layout == "tiled":
        _run_tmux("select-layout", "-t", f"{session}:0", "tiled", check=False)

    # The new pane is the last one.  Get its index.
    result = _run_tmux("display-message", "-t", f"{session}:0", "-p", "#{pane_index}")
    pane_idx = result.stdout.strip() or "0"
    return f"{session}:0.{pane_idx}"


def _send_command(pane_target: str, command: str) -> None:
    """Send a shell command to a tmux pane."""
    _run_tmux("send-keys", "-t", pane_target, command, "Enter")


def _apply_layout(session: str, layout: str) -> None:
    """Apply the final layout to all panes."""
    layout_map = {
        "tiled": "tiled",
        "vertical": "even-vertical",
        "horizontal": "even-horizontal",
    }
    tmux_layout = layout_map.get(layout, "tiled")
    _run_tmux("select-layout", "-t", f"{session}:0", tmux_layout, check=False)


# ---------------------------------------------------------------------------
# Worker dispatch
# ---------------------------------------------------------------------------


def _write_prompt_file(worker_id: str, prompt: str) -> Path:
    """Write a worker prompt to a temp file and return the path."""
    fd, path = tempfile.mkstemp(prefix=f"stp-worker-{worker_id}-prompt-", suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(prompt)
    return Path(path)


def _build_worker_prompt(worker: dict[str, Any], build_prompt_script: Path) -> str:
    """Build a prompt for a worker using build_prompt.py logic inlined.

    Falls back to a simple concatenation if the build_prompt module cannot be
    imported (e.g., missing agent file).
    """
    # Try to import build_prompt from the same directory.
    try:
        sys.path.insert(0, str(build_prompt_script.parent))
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

    # Fallback: simple prompt.
    parts = [f"You are the {worker['agent']} agent.\n"]
    for fp_str in worker.get("input_files", []):
        fp = Path(fp_str)
        if fp.is_file():
            parts.append(f"## File: {fp.name}\n{fp.read_text(encoding='utf-8')}\n")
    parts.append("Produce your findings in structured Markdown.\n")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Status tracking
# ---------------------------------------------------------------------------


class WorkerStatus:
    """Track status of a single worker."""

    def __init__(self, worker_id: str, pane_target: str, output_file: Path) -> None:
        self.worker_id = worker_id
        self.pane_target = pane_target
        self.output_file = output_file
        self.status: str = "RUNNING"
        self.start_time: float = time.time()
        self.end_time: Optional[float] = None

    @property
    def elapsed(self) -> float:
        end = self.end_time if self.end_time else time.time()
        return end - self.start_time

    def check(self) -> str:
        """Check if the worker has completed."""
        if self.status != "RUNNING":
            return self.status

        if self.output_file.is_file():
            try:
                content = self.output_file.read_text(encoding="utf-8", errors="replace")
                if WORKER_DONE_SENTINEL in content:
                    self.status = "DONE"
                    self.end_time = time.time()
                    return self.status
            except OSError:
                pass

        return self.status

    def check_timeout(self, timeout: int) -> bool:
        """Mark as TIMEOUT if elapsed exceeds the limit. Returns True if timed out."""
        if self.status == "RUNNING" and self.elapsed > timeout:
            self.status = "TIMEOUT"
            self.end_time = time.time()
            return True
        return False

    def finalize(self) -> None:
        """Final status check after monitoring loop."""
        if self.status == "RUNNING":
            # Process ended but no sentinel found.
            if self.output_file.is_file():
                size = self.output_file.stat().st_size
                if size == 0:
                    self.status = "FAILED"
                else:
                    # Output exists but no sentinel -- treat as done.
                    self.status = "DONE"
            else:
                self.status = "FAILED"
            self.end_time = time.time()


def _print_status_line(workers: list[WorkerStatus]) -> None:
    """Print a single-line status summary."""
    parts = []
    for ws in workers:
        parts.append(f"[{ws.worker_id}] {ws.status}")
    print("  " + " | ".join(parts), flush=True)


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


def run_workers_in_tmux(
    session: str,
    work_plan: dict[str, Any],
    output_dir: Path,
    timeout: int = DEFAULT_TIMEOUT,
    layout: str = "tiled",
    cleanup: bool = False,
) -> list[dict[str, Any]]:
    """Dispatch workers into tmux panes and monitor until completion.

    Returns a list of worker result dicts.
    """
    # Ensure tmux is available.
    if not shutil.which("tmux"):
        print(
            "Error: tmux is not installed. Install it or use non-tmux mode.",
            file=sys.stderr,
        )
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    build_prompt_script = Path(__file__).resolve().parent / "build_prompt.py"

    # Create or attach to session.
    if not _tmux_session_exists(session):
        _create_session(session)
        print(f"Created tmux session: {session}")
    else:
        print(f"Attaching to existing tmux session: {session}")

    workers_spec: list[dict[str, Any]] = work_plan.get("workers", [])
    if not workers_spec:
        print("Error: no workers in work plan.", file=sys.stderr)
        sys.exit(1)

    statuses: list[WorkerStatus] = []

    for i, worker in enumerate(workers_spec):
        worker_id = worker.get("id", f"worker-{i + 1}")
        output_file = Path(worker.get("output_file", str(output_dir / f"{worker_id}.md")))
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Build and write prompt.
        prompt = _build_worker_prompt(worker, build_prompt_script)
        prompt_file = _write_prompt_file(worker_id, prompt)

        # Create pane.
        pane_target = _create_pane(session, worker_id, layout, first=(i == 0))

        # Build the shell command.
        model_flag = ""
        model = worker.get("model", "")
        if model:
            model_flag = f" --model {model}"

        shell_cmd = (
            f"claude --print --dangerously-skip-permissions{model_flag} "
            f'-p "$(cat {prompt_file})" > {output_file} 2>&1; '
            f'echo "{WORKER_DONE_SENTINEL}" >> {output_file}'
        )
        _send_command(pane_target, shell_cmd)

        ws = WorkerStatus(worker_id, pane_target, output_file)
        statuses.append(ws)

        print(f"  Dispatched {worker_id} ({worker.get('agent', '?')}) -> pane {pane_target}")

    # Apply final layout.
    _apply_layout(session, layout)

    # Monitor loop.
    print(f"\nMonitoring {len(statuses)} workers (timeout={timeout}s)...")
    while True:
        all_done = True
        for ws in statuses:
            ws.check()
            ws.check_timeout(timeout)
            if ws.status == "RUNNING":
                all_done = False

        _print_status_line(statuses)

        if all_done:
            break

        time.sleep(POLL_INTERVAL)

    # Finalize any stragglers.
    for ws in statuses:
        ws.finalize()

    # Print summary.
    print("\n--- Worker Summary ---")
    print(f"{'ID':<20} {'Status':<10} {'Elapsed':>10}")
    print("-" * 42)
    results: list[dict[str, Any]] = []
    for ws in statuses:
        elapsed_str = f"{ws.elapsed:.1f}s"
        print(f"{ws.worker_id:<20} {ws.status:<10} {elapsed_str:>10}")
        results.append(
            {
                "id": ws.worker_id,
                "status": ws.status,
                "elapsed_seconds": round(ws.elapsed, 2),
                "output_file": str(ws.output_file),
            }
        )

    # Cleanup.
    if cleanup:
        print(f"\nKilling tmux session: {session}")
        _run_tmux("kill-session", "-t", session, check=False)
    else:
        print(f"\nTmux session '{session}' left running for inspection.")
        print(f"  Attach with: tmux attach -t {session}")

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage Claude CLI workers inside tmux sessions.",
    )
    parser.add_argument(
        "--session",
        default="stp-workers",
        help="Tmux session name (default: stp-workers)",
    )
    parser.add_argument(
        "--workers",
        type=Path,
        required=True,
        help="Path to work plan JSON file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output directory for worker results",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Per-worker timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Kill the tmux session when all workers complete",
    )
    parser.add_argument(
        "--layout",
        choices=["tiled", "vertical", "horizontal"],
        default="tiled",
        help="Pane layout: tiled, vertical, or horizontal (default: tiled)",
    )
    args = parser.parse_args()

    if not args.workers.is_file():
        print(f"Error: work plan not found: {args.workers}", file=sys.stderr)
        sys.exit(1)

    work_plan = json.loads(args.workers.read_text(encoding="utf-8"))

    results = run_workers_in_tmux(
        session=args.session,
        work_plan=work_plan,
        output_dir=args.output,
        timeout=args.timeout,
        layout=args.layout,
        cleanup=args.cleanup,
    )

    # Write results summary.
    summary_path = args.output / "tmux-run-summary.json"
    summary_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"\nRun summary written to {summary_path}")


if __name__ == "__main__":
    main()
