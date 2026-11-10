# Bind delivery to the source actually checked

Freeze the source commit and tree after required checks pass. Record the exact
commands, exit status and retained logs; a model's summary is not a substitute
for a process result. Preserve failed and interrupted attempts in distinct paths.
A missing terminal receipt means incomplete, even if its log contains a passing
summary. Never run a second writer against an earlier attempt's log.

Bind each independent review to that source tree, its angle, verdict and retained
record. Follow the target repository's reviewer-count and independence rules;
do not export a project's three-review policy to unrelated projects. An author
does not count as an independent reviewer of their own work. Repairs need the
affected checks/reviews again. Unchanged source may retain its earlier evidence
when the binding and environment still apply; record that reuse explicitly.

Before an authorized merge, refresh the PR head, base and actual required CI
results. Distinguish a PR head from the synthetic merge commit CI tested. If the
base or head changes, establish the new relationship and repeat affected checks;
never transfer a green status simply because the PR number stayed the same.
After merge, verify the returned merge commit and its tree against the qualified
tree. A squash can change commit identity while preserving the tree.

For work using external writers or sandbox workers, retain the owning
controller's stopped-state readback and exact resource identities. An exec
timeout or terminated client does not prove a remote worker stopped. Unknown
custody remains unknown. Do not replace a denied lifecycle operation with an
improvised process-control path. Use `not_applicable` only when no such writer
was part of the task, and state why.

Keep source delivery, package build, installation, live verification, migration
and final acceptance separate. An authorized source merge does not authorize a
live deployment or immutable task acceptance. Report measured limits and failed
performance gates independently from correctness.

## Offline consistency check

From the loaded plugin root, run:

```sh
python3 scripts/verify-delivery.py /private/evidence/delivery.json --checkout /path/to/clean-checkout --required-reviewers 3
```

Choose the reviewer count from the target repository's policy. The example's
three is illustrative. This command reads only the declared packet/artifacts
and local Git objects; it neither executes tests nor contacts GitHub. It checks
hashes, matching source trees, declared successful results and stopped custody.
It cannot authenticate reviewer identities, prove the packet includes every
failed attempt, prove log text came from the declared command, or establish
current remote CI/merge state. The coordinator must inspect those provenance
and live-state facts separately. Its output is advisory, never approval.

The checkout must be clean, including untracked files. Keep the packet and
artifacts outside it. The checkout may be at the source commit or a merge commit
with the same tree. Ensure the declared source, CI-tested and merged commits
are already available locally. The verifier does not fetch them.

Packet shape (`COMMIT`, `TREE`, and `SHA256` stand for complete actual hashes):

```json
{
  "schema": "ship-loop.delivery.v1",
  "source": {"commit": "COMMIT", "tree": "TREE", "authors": ["implementer"]},
  "verifications": [{
    "source_tree": "TREE", "argv": ["python3", "check.py"], "exit_code": 0,
    "log": {"path": "checks.log", "sha256": "SHA256"}
  }],
  "reviews": [{
    "reviewer": "independent-reviewer", "source_tree": "TREE", "verdict": "pass",
    "record": {"path": "review.json", "sha256": "SHA256"}
  }],
  "ci": {
    "head_commit": "COMMIT", "tested_commit": "CI_COMMIT", "tested_tree": "TREE",
    "conclusion": "success", "record": {"path": "ci.json", "sha256": "SHA256"}
  },
  "custody": {"status": "stopped", "record": {"path": "owner.json", "sha256": "SHA256"}},
  "retained_failures": [{"path": "earlier-failure.log", "sha256": "SHA256"}],
  "merge_commit": "MERGED_COMMIT"
}
```

Supply one review row per required independent reviewer. `merge_commit` is
optional before merge. `retained_failures` may be empty when there were none.
For tasks without external writers, custody is
`{"status":"not_applicable","reason":"No external writers were used"}`.
Artifact paths are relative to the packet directory; escaping paths, final
symlinks, non-regular files and hash mismatches are refused. Packets are bounded
to 1 MiB and each artifact to 64 MiB. Use a retained bounded summary with links
to raw evidence for larger artifacts, and disclose that distinction.
