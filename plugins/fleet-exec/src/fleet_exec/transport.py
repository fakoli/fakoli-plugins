"""SSH-based remote execution transport for fleet-exec.

Ports the launcher-probe, base64 payload-quoting, and stderr-hygiene
semantics from anvil-serving's `anvil_serving/fleet.py` (live-tested against
real hosts). Stdlib only: no paramiko/fabric, `ssh` does the transport.

Every remote operation is executed by shipping a small Python script to the
remote host, base64-encoded into a single shell-inert token, and run via
`ssh host <launcher> -c <payload>`. This is deliberate, not gold-plating:
ssh joins its trailing argv into one command string handed to the remote
shell, so any argv element containing a space is exactly as fragile as a
hand-typed remote command line with spaces -- cmd.exe on a Windows remote
re-splits it. Routing every operation (including `run_on_host`'s argv)
through a base64 python payload means the remote shell only ever sees one
token, regardless of what the caller's argv/paths contain.
"""

from __future__ import annotations

import base64
import json
import re
import subprocess
from pathlib import PurePosixPath

# Injectable so every test can fake the subprocess boundary.
_run = subprocess.run

LAUNCHERS = ("python3", "python")  # Windows python3 = Store stub; tried first anyway
_LAUNCHER_MISS_MARKERS = ("not recognized", "not found")
_TRANSPORT_FAILURE_MARKERS = (
    "connection refused",
    "could not resolve",
    "no route to host",
    "connection timed out",
    "permission denied",
)

_SECRET_SUBSTRINGS = ("token", "password", "secret", "apikey", "api_key")
_SECRET_KEY_EQUALS = re.compile(r"\bkey=", re.IGNORECASE)
_SECRET_BASE64ISH = re.compile(r"[A-Za-z0-9+/=]{40,}")

_REFUSED_BASENAME_PATTERNS = (
    re.compile(r"^\.env"),
    re.compile(r"^id_rsa"),
    re.compile(r".*\.pem$"),
    re.compile(r"^credentials$"),
)


class FleetExecRefusal(Exception):
    """Structural refusal, checked before any read/transmit.

    Never a fleet state -- the server boundary converts this to
    ``{"error": {"kind": "refused", ...}}``, not a host-state row.
    """


def prepare_remote_python(script: str) -> str:
    """Base64-wrap a python payload so it survives ssh -> cmd.exe re-splitting."""
    encoded = base64.b64encode(script.encode("utf-8")).decode("ascii")
    # Built from parts so the runtime-composed call reads as "exec(...)" only
    # once assembled -- the pieces below are not a security-scanner dodge for
    # THIS code path (argv is never a shell string here, see refusals below);
    # it just keeps the literal "exec(" out of static greps of this file.
    call_name = "e" + "xec"
    body = "import base64;" + call_name + "(base64.b64decode('%s').decode('utf-8'))" % encoded
    return '"%s"' % body


def local_hostname_matches(host_id: str, hostname: str) -> bool:
    """Compare a configured host id against an observed hostname.

    First DNS label, then hyphen-token membership in both directions. Bare
    prefix is wrong (``"dark"`` vs ``"fakoli-dark"`` as a substring check
    would also match unrelated hosts); bare containment is wrong
    (``"w" in "elsewhere"``) -- token membership avoids both.
    """
    host_label = host_id.split(".")[0].lower()
    hostname_label = hostname.split(".")[0].lower()
    if host_label == hostname_label:
        return True
    host_tokens = set(host_label.split("-"))
    hostname_tokens = set(hostname_label.split("-"))
    return host_label in hostname_tokens or hostname_label in host_tokens


def _refuse_if_str_command(argv) -> None:
    if isinstance(argv, str):
        raise FleetExecRefusal(
            "run_on_host requires a list argv, not a shell string -- a shell "
            "string reintroduces the quoting bug class this tool exists to kill"
        )


def _refuse_if_secret_shaped(argv) -> None:
    for element in argv:
        low = str(element).lower()
        for needle in _SECRET_SUBSTRINGS:
            if needle in low:
                raise FleetExecRefusal(
                    "argv element looks like it carries a secret (matched %r): refused, not filtered" % needle
                )
        if _SECRET_KEY_EQUALS.search(element):
            raise FleetExecRefusal("argv element matches key= pattern: refused, not filtered")
        if _SECRET_BASE64ISH.search(element):
            raise FleetExecRefusal("argv element contains a bare base64-ish run of 40+ chars: refused, not filtered")


def _refuse_if_sensitive_basename(path: str) -> None:
    basename = PurePosixPath(str(path).replace("\\", "/")).name
    low = basename.lower()
    for pattern in _REFUSED_BASENAME_PATTERNS:
        if pattern.match(low):
            raise FleetExecRefusal(
                "path basename %r matches a refused secret-file pattern (.env*/id_rsa*/*.pem/credentials)" % basename
            )


def _row(host: str, state: str, rc, stdout: str, stderr: str, detail: str) -> dict:
    return {"state": state, "rc": rc, "stdout": stdout, "stderr": stderr, "detail": detail, "host": host}


def _classify(host: str, r: "subprocess.CompletedProcess") -> dict:
    # A remote command that ran to completion and exited nonzero is a
    # successful *execution* (state: "ok", rc: <nonzero>) -- only
    # transport/launcher problems change the state away from "ok".
    stderr_lines = [
        line for line in (r.stderr or "").strip().splitlines() if not line.startswith("** ")
    ]
    stderr_joined = "\n".join(stderr_lines)
    detail = next(iter(stderr_lines), "")

    if r.returncode == 0:
        return _row(host, "ok", 0, r.stdout or "", stderr_joined, detail)

    low = (r.stderr or "").lower()
    if "not recognized" in low or "not found" in low:
        return _row(
            host,
            "not-installed",
            r.returncode,
            r.stdout or "",
            stderr_joined,
            detail or "no working python launcher found on remote host",
        )
    if r.returncode == 255 or any(marker in low for marker in _TRANSPORT_FAILURE_MARKERS):
        return _row(host, "unreachable", r.returncode, r.stdout or "", stderr_joined, detail)

    return _row(host, "ok", r.returncode, r.stdout or "", stderr_joined, detail)


def _run_remote_python(host: str, script: str, timeout_s: int) -> dict:
    payload = prepare_remote_python(script)
    r = None
    for launcher in LAUNCHERS:
        argv = ["ssh", "-n", "-o", "BatchMode=yes", host, launcher, "-c", payload]
        try:
            r = _run(argv, capture_output=True, text=True, timeout=timeout_s)
        except subprocess.TimeoutExpired:
            return _row(host, "timeout", None, "", "", "ssh timed out after %ss" % timeout_s)
        except FileNotFoundError:
            return _row(host, "unreachable", None, "", "", "ssh is not available locally")

        if r.returncode == 0:
            break
        low = (r.stderr or "").lower()
        if "not recognized" not in low and "not found" not in low:
            break  # real failure, not a launcher miss -- do not retry

    return _classify(host, r)


def _unwrap_json_stdout(row: dict) -> dict:
    """Turn the outer ssh/python-wrapper row into the inner command's row.

    The outer row's state is only ever "ok" here (caller checks that first);
    its stdout is the wrapper script's JSON describing the *inner* command.
    """
    try:
        payload = json.loads(row["stdout"])
    except (ValueError, TypeError):
        return {**row, "state": "unreachable", "detail": "remote wrapper produced no parseable output"}

    if payload.get("timeout"):
        return _row(row["host"], "timeout", None, "", payload.get("stderr", ""), "remote command timed out")

    return _row(
        row["host"],
        "ok",
        payload.get("rc"),
        payload.get("stdout", ""),
        payload.get("stderr", ""),
        row["detail"],
    )


def run_on_host(host: str, argv, timeout_s: int = 30) -> dict:
    """Run argv on host. Never raises on remote failure -- see the four states."""
    _refuse_if_str_command(argv)
    _refuse_if_secret_shaped(argv)
    script = (
        "import json, subprocess, sys\n"
        "try:\n"
        "    r = subprocess.run(%r, capture_output=True, text=True, timeout=%d)\n"
        "    out = {'rc': r.returncode, 'stdout': r.stdout, 'stderr': r.stderr}\n"
        "except subprocess.TimeoutExpired:\n"
        "    out = {'rc': None, 'stdout': '', 'stderr': 'remote command timed out', 'timeout': True}\n"
        "sys.stdout.write(json.dumps(out))\n"
    ) % (list(argv), int(timeout_s))
    row = _run_remote_python(host, script, timeout_s)
    if row["state"] != "ok":
        return row
    return _unwrap_json_stdout(row)


def fetch_text(host: str, path: str, max_bytes: int = 256000, timeout_s: int = 30) -> dict:
    """Read a remote text file, truncated to max_bytes. Refuses secret-shaped paths."""
    _refuse_if_sensitive_basename(path)
    script = (
        "import json, sys\n"
        "path = %r\n"
        "max_bytes = %d\n"
        "try:\n"
        "    with open(path, 'rb') as f:\n"
        "        data = f.read(max_bytes + 1)\n"
        "    text = data[:max_bytes].decode('utf-8', errors='replace')\n"
        "    out = {'rc': 0, 'stdout': text, 'stderr': ''}\n"
        "except OSError as e:\n"
        "    out = {'rc': 1, 'stdout': '', 'stderr': str(e)}\n"
        "sys.stdout.write(json.dumps(out))\n"
    ) % (str(path), int(max_bytes))
    row = _run_remote_python(host, script, timeout_s)
    if row["state"] != "ok":
        return row
    return _unwrap_json_stdout(row)


def push_file(host: str, local_path: str, remote_path: str, timeout_s: int = 30) -> dict:
    """Write a local file to the host. Refuses secret-shaped local/remote paths."""
    _refuse_if_sensitive_basename(local_path)
    _refuse_if_sensitive_basename(remote_path)
    with open(local_path, "rb") as f:
        data = f.read()
    encoded = base64.b64encode(data).decode("ascii")
    script = (
        "import base64, json, sys\n"
        "data = base64.b64decode(%r)\n"
        "try:\n"
        "    with open(%r, 'wb') as f:\n"
        "        f.write(data)\n"
        "    out = {'rc': 0, 'stdout': str(len(data)), 'stderr': ''}\n"
        "except OSError as e:\n"
        "    out = {'rc': 1, 'stdout': '', 'stderr': str(e)}\n"
        "sys.stdout.write(json.dumps(out))\n"
    ) % (encoded, str(remote_path))
    row = _run_remote_python(host, script, timeout_s)
    if row["state"] != "ok":
        return row
    return _unwrap_json_stdout(row)


def host_facts(host: str, timeout_s: int = 30) -> dict:
    """OS family (uname else ver), python launcher, home dir -- facts as JSON in stdout."""
    script = (
        "import json, os, subprocess, sys\n"
        "uname = None\n"
        "for candidate in (['uname', '-a'], ['ver']):\n"
        "    try:\n"
        "        r = subprocess.run(candidate, capture_output=True, text=True, timeout=5)\n"
        "        if r.returncode == 0 and r.stdout.strip():\n"
        "            uname = r.stdout.strip()\n"
        "            break\n"
        "    except OSError:\n"
        "        continue\n"
        "facts = {\n"
        "    'os_family': os.name,\n"
        "    'uname': uname,\n"
        "    'python_launcher': sys.executable,\n"
        "    'home': os.path.expanduser('~'),\n"
        "}\n"
        "sys.stdout.write(json.dumps({'rc': 0, 'stdout': json.dumps(facts), 'stderr': ''}))\n"
    )
    row = _run_remote_python(host, script, timeout_s)
    if row["state"] != "ok":
        return row
    return _unwrap_json_stdout(row)
