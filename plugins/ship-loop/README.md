# ship-loop

The full shipping procedure as one invocable skill: take a feature or fix
from idea to merged PR with a **multi-angle adversarial review as the merge
gate** — plus the isolation, ground-truthing, and follow-up discipline that
makes long-running multi-agent repos stay coherent.

## The loop

| Step | What | The rule that earns its keep |
|---|---|---|
| 1 | Sync + isolate | `git fetch` first; build in a worktree off `origin/main` — the main checkout may belong to another agent mid-flight |
| 2 | Scope | Explore agents with precise questions; **verify every load-bearing assumption against on-disk reality**, not docs |
| 3 | Implement | Mirror the repo's precedents; guards fail **closed**; fix-or-file anything broken you trip over |
| 4 | Test | Fixtures byte-faithful to real formats — a fixture that mirrors your assumption *certifies* your bug |
| 5 | **Adversarial review** | 8 finder angles over the diff; the **cross-process boundary tracer is non-negotiable** (three consecutive PRs' worst bugs lived at process boundaries); findings verified against ground truth; fix or record rationale |
| 6 | Ship | CHANGELOG with BREAKING callouts, PR with testing evidence, CI watch, squash-merge, worktree cleanup (composes with `/ship`, ship-task plugin) |
| 7 | Close the loop | Update the promotions ledger, file out-of-diff issues, promote durable lessons |

## Why a skill and not memory

Memory recalls *policy* ("review before merge"); a skill encodes the
*procedure* — deterministic steps, the platform gotchas (Windows heredoc
backslash mangling, `.cmd` spawn hardening, cp1252 output), and the review
angles, invocable identically from Claude Code and Codex.

## Provenance

Distilled from three consecutive PR cycles run with this exact process
(fakoli-plugins#128 anvil-pulse, anvil-serving#186 host guard, anvil#169
worktree isolation + distinct-actor fail-fast), where the review gate caught
production-breaking bugs a green test suite had certified — every time at a
process boundary.

## Use

- Claude Code: `/ship-loop <what to ship>` or "ship this the usual way"
- Codex: invoke the `ship-loop:ship-loop` skill

No scripts, no dependencies — the skill is the procedure.

## License

MIT
