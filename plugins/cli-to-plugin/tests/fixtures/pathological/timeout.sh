#!/usr/bin/env bash
# timeout.sh — A script that sleeps 6 seconds before printing any output.
#
# Purpose: test that discover.py enforces the per-call timeout (default 5s).
# When discover.py runs this script as a subprocess, the 5s timeout should
# fire before the script prints anything, causing discover.py to:
#   1. Kill the subprocess
#   2. Log a warning: "timeout after 5s fetching help for <command>"
#   3. Continue discovery (skip this command) rather than aborting
#
# Usage in tests:
#   monkeypatch subprocess so that calling `./timeout.sh --help` invokes this script.
#   Assert that the discovery result includes a "timeout" warning entry.
#
# The 6-second sleep is intentionally 1 second longer than the default 5s timeout.

sleep 6

echo "If you see this, the timeout did not fire — test should FAIL."
echo ""
echo "SLOWCLI — Help output that arrives too late."
echo ""
echo "USAGE"
echo "  slowcli <command> [flags]"
echo ""
echo "COMMANDS"
echo "  run:    Run something (slowly)"
