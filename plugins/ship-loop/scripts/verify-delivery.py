#!/usr/bin/env python3
"""Check retained delivery evidence against a clean local Git checkout.

This checks consistency, artifact hashes and Git objects. It does not authenticate
reviewers, fetch current CI, or grant publication, merge or acceptance authority.
"""
import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path

MAX_PACKET_BYTES = 1024 * 1024
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def object_id(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value),
            "Git identities must be full lowercase object IDs")
    return value


def git(checkout, *arguments):
    result = subprocess.run(["git", "-C", str(checkout), *arguments],
                            capture_output=True, text=True, timeout=30)
    require(result.returncode == 0, "Git object or checkout check failed")
    return result.stdout.strip()


def read_regular(path, maximum):
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)
                         | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        require(stat.S_ISREG(metadata.st_mode), "Evidence must be a regular file")
        require(metadata.st_size <= maximum, "Evidence exceeds its byte limit")
        data = stream.read(maximum + 1)
    require(len(data) <= maximum, "Evidence exceeds its byte limit")
    return data


def artifact(packet_directory, reference):
    require(isinstance(reference, dict), "Missing artifact reference")
    relative = reference.get("path")
    digest = reference.get("sha256")
    require(isinstance(relative, str) and relative and not Path(relative).is_absolute(),
            "Artifact paths must be relative to the packet")
    require(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest),
            "Artifact SHA256 is required")
    candidate = packet_directory / relative
    require(not candidate.is_symlink(), "Artifact symlinks are not accepted")
    candidate = candidate.resolve(strict=True)
    require(candidate.is_relative_to(packet_directory), "Artifact escapes the packet directory")
    data = read_regular(candidate, MAX_ARTIFACT_BYTES)
    require(hashlib.sha256(data).hexdigest() == digest, "Artifact hash mismatch: " + relative)
    return relative


def verify(packet_path, checkout, required_reviewers):
    require(required_reviewers >= 1, "At least one reviewer is required")
    packet_path = Path(packet_path).resolve(strict=True)
    raw = read_regular(packet_path, MAX_PACKET_BYTES)
    packet = json.loads(raw)
    require(isinstance(packet, dict) and packet.get("schema") == "ship-loop.delivery.v1",
            "Unsupported delivery packet")
    directory = packet_path.parent
    source = packet["source"]
    commit = object_id(source["commit"])
    tree = object_id(source["tree"])
    require(git(checkout, "rev-parse", commit + "^{tree}") == tree, "Source tree mismatch")
    require(git(checkout, "rev-parse", "HEAD^{tree}") == tree, "Checkout tree mismatch")
    require(not git(checkout, "status", "--porcelain=v1", "--untracked-files=all"),
            "Checkout must be clean; retain evidence outside it")
    authors = source.get("authors")
    require(isinstance(authors, list) and authors and all(isinstance(x, str) and x for x in authors),
            "Declare source authors before checking independent reviews")
    tests = packet["verifications"]
    require(isinstance(tests, list) and tests, "Actual verification receipts are required")
    retained = []
    for test in tests:
        require(test["source_tree"] == tree, "Verification source tree mismatch")
        require(type(test["exit_code"]) is int and test["exit_code"] == 0,
                "Required verification did not exit zero")
        require(isinstance(test["argv"], list) and test["argv"]
                and all(isinstance(x, str) and x for x in test["argv"]), "Actual argv is required")
        retained.append(artifact(directory, test["log"]))
    reviews = packet["reviews"]
    require(isinstance(reviews, list) and len(reviews) >= required_reviewers,
            "Missing required independent review")
    reviewer_ids = set()
    for review in reviews:
        reviewer = review["reviewer"]
        require(isinstance(reviewer, str) and reviewer and reviewer not in authors
                and reviewer not in reviewer_ids, "Reviewer must be distinct from authors and other reviewers")
        reviewer_ids.add(reviewer)
        require(review["source_tree"] == tree and review["verdict"] == "pass",
                "Review is stale or has not passed")
        retained.append(artifact(directory, review["record"]))
    ci = packet["ci"]
    require(ci["head_commit"] == commit and ci["tested_tree"] == tree
            and ci["conclusion"] == "success", "CI is unsuccessful or bound to different source")
    require(git(checkout, "rev-parse", object_id(ci["tested_commit"]) + "^{tree}") == tree,
            "CI tested commit has a different tree")
    retained.append(artifact(directory, ci["record"]))
    custody = packet["custody"]
    require(custody["status"] in {"stopped", "not_applicable"}, "Writer stop is unknown or incomplete")
    if custody["status"] == "stopped":
        retained.append(artifact(directory, custody["record"]))
    else:
        require(isinstance(custody.get("reason"), str) and custody["reason"].strip(),
                "Explain why external writer custody is not applicable")
    failures = packet["retained_failures"]
    require(isinstance(failures, list), "Retained failures must be listed explicitly")
    for failure in failures:
        retained.append(artifact(directory, failure))
    merged = packet.get("merge_commit")
    if merged is not None:
        require(git(checkout, "rev-parse", object_id(merged) + "^{tree}") == tree,
                "Merged tree differs from qualified source")
    return {"consistent": True, "source_commit": commit, "source_tree": tree,
            "merge_commit": merged, "verifications": len(tests), "reviewers": len(reviewer_ids),
            "retained_failures": len(failures), "artifacts_checked": len(retained),
            "scope": "Offline consistency and local Git objects only; refresh remote CI and verify provenance separately."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", help="Private retained delivery packet JSON")
    parser.add_argument("--checkout", required=True, help="Clean local checkout containing the declared Git objects")
    parser.add_argument("--required-reviewers", type=int, required=True,
                        help="Count from the target repository's review policy")
    args = parser.parse_args()
    try:
        result = verify(args.packet, args.checkout, args.required_reviewers)
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as error:
        print(json.dumps({"consistent": False, "error": str(error)}, ensure_ascii=True))
        return 1
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
