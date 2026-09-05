#!/usr/bin/env python3
"""Extract literal plugin-root paths from shell argv without evaluating shell code."""
import json
import shlex
import sys


def paths(command):
    prefixes = ('${CLAUDE_PLUGIN_ROOT}/', '${PLUGIN_ROOT}/')
    tokens = shlex.split(command)
    found = []
    for token in tokens:
        for prefix in prefixes:
            if token.startswith(prefix):
                found.append(token[len(prefix):])
    return found


if __name__ == '__main__':
    try:
        print(json.dumps(paths(sys.argv[1])))
    except (IndexError, ValueError) as exc:
        print(f'Cannot parse hook command: {exc}', file=sys.stderr)
        raise SystemExit(1)
