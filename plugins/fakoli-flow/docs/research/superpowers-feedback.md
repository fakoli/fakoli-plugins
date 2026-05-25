# SuperPowers Plugin: User Feedback Research

Researched: 2026-04-02
Repo: https://github.com/obra/superpowers
Official listing: https://claude.com/plugins/superpowers
HN rave review: https://news.ycombinator.com/item?id=47623101
HN original announcement: https://news.ycombinator.com/item?id=45547344

---

## Repository Statistics (as of 2026-04-02)

- Stars: 135,029 (launched October 9, 2025 — ~6 months to 135k stars)
- Forks: 11,289
- Open issues: 222
- Open bug-labeled issues: 64
- Last push: 2026-04-02 (active daily)
- License: MIT
- Language: Shell
- Latest release: v5.0.7 (2026-03-31)
- Official Anthropic marketplace: accepted January 15, 2026

## Main Contributors

obra (Jesse Vincent, Prime Radiant), plus arittr, clkao, jjshanks, karuturi,
savvyinsight, mvanhorn, abzhaw, atian8179, avleen, daniel-graham, and many
community contributors. The project is community-driven with open issues,
and Claude itself files and comments on issues regularly.

---

## What Users Like

### 1. The Structured Workflow Forces Better Outcomes

The core value proposition that users consistently validate: SuperPowers prevents
Claude from jumping directly into code by enforcing a Brainstorm → Plan → Implement
sequence. Multiple independent reviewers confirm this produces materially better
results than stock Claude Code.

Evan Schwartz (rave review author, blog.emschwartz.me):
> "Using Claude Code with Superpowers is so much more productive and the features
> it builds are so much more correct than with stock Claude Code."

> "I feel better about tradeoffs being made and much more confident that the code
> written does what I want."

Richard Porter (richardporter.dev):
> "Features spanning 15+ files now execute consistently, whereas previously Claude
> would lose track of earlier decisions or produce contradictory code."

Trevor Lasn (trevorlasn.com):
> "It skips steps constantly. It starts suggesting changes immediately. No planning
> phase. That's how you miss files. That's how you ship bugs."
> (SuperPowers solves this.)

### 2. Options + Tradeoffs Presentation

A frequently praised feature: after brainstorming, Claude presents multiple
implementation approaches with explicit tradeoffs before committing to any.

Evan Schwartz:
> "After asking questions, it will present multiple options with tradeoffs —
> allowing developers to evaluate choices before committing to implementation details."

### 3. Editable Markdown Design Docs

The spec/plan output is a markdown file in the repository that users can open,
edit, and comment on in their own editor.

Schwartz: "One friend found this way more empowering than Claude Code's normal UX."

### 4. Brainstorming Skill Quality

HN commenter tao_oat:
> "The brainstorming skill is great. It helps flesh out a rough early idea."

DevelopersIO reviewer (Japanese developer):
> "Questions come one at a time. Being asked 10 questions at once is stressful,
> but answering in this one-by-one format is manageable."
> "Specifications that were initially vague become clear through the dialogue."

### 5. Self-Improvement / Skill Authoring

Jesse Vincent (creator, blog.fsck.com):
> "You can hand a model a book or document or codebase and say 'Read this.
> Write down the new stuff you learned.'"

Users value being able to write their own skills and having Claude generate new
skills from observed patterns.

### 6. Visual Brainstorming Companion

Evan Schwartz:
> "Claude builds simple mock-ups for UI changes and other visual features, starting
> a local dev server so you can review, discuss, and iterate on the mock-ups before
> proceeding."

Simon Willison called the Root Cause Tracing skill "particularly fun" because
Claude can interpret Graphviz diagrams as workflow instructions.

### 7. TDD Enforcement

Abirch (HN): highlighted TDD as a distinguishing feature worth adoption.

Richard Porter:
> "The framework forces test-driven development before implementation, producing
> comprehensive test coverage by default, not as an afterthought."

### 8. Git Worktrees Automation

Jesse Vincent: Claude automatically creates a git worktree once planning concludes,
enabling parallel tasks without conflicts. Simon Willison specifically flagged this
as a significant capability.

---

## What Users Dislike

### 1. Token Consumption is High

**Issue #190**: All 14+ skills are fully loaded at session startup, consuming ~22k
tokens (11% of the 200k context window) before any work begins.

From the issue body, precise measurements at startup:
```
writing-skills:                  5.6k tokens
test-driven-development:         2.4k tokens
systematic-debugging:            2.4k tokens
subagent-driven-development:     2.4k tokens
[... 10 more skills ...]
Total:                          ~22k tokens
```

This is 15.7x more than the ~1,400 tokens expected if only metadata (name +
description) were loaded. The Anthropic docs describe progressive disclosure, but
SuperPowers does not implement it.

**Issue #953**: A user gave Claude a simple task (add Google Calendar as an MCP
server) and hit 100% quota in 5 minutes because SuperPowers triggered documentation
writing and other overhead the user didn't ask for.

**Issue #750**: Users on OpenCode + Codex report "a lot of tokens" consumed
compared to previous versions.

HN commenter gtirloni: "Eventually, Plan mode became enough and I prefer to steer
Claude Code myself." Reason: SuperPowers frameworks "consume substantially more
tokens, hitting subscription limits without commensurate quality improvements."

### 2. Plans Over-Specify Implementation

**Issue #895** (13 comments, highly active): The `writing-plans` skill generates
plans containing complete implementation code — full function bodies, 70-line test
files, exact shell commands, step-by-step TDD sequences. The executor then has no
decisions to make and is essentially copy-pasting code from the plan rather than
engineering a solution.

Two concrete problems from the issue:
1. When implementation revealed a better approach mid-execution, the plan's code
   was wrong even though the intent was still valid. Adapting meant "violating" the plan.
2. Every task duplicated the TDD ceremony that executing-plans and test-driven-
   development already enforce, bloating each task from ~20 lines to 80-100+.

Multiple community members validated this:
- "If a planning skill is writing the entire implementation, why not just have it
  put that code in a .py file instead of .md?"
- "Subagents with less used context perform better. That's why I don't understand
  where's the value in leaving the planning agent do all the implementation work."
- Jesse Vincent's own response acknowledges the problem but no fix is merged yet.

### 3. Subagents Don't Receive Discipline Context

**Issue #237** (detailed, reproducible): When dispatching a subagent, the subagent
can see the skill list but does NOT receive the using-superpowers hook-injected
content. This means subagents lack the discipline framework (Red Flags table, TDD
habits, skill-first behavior).

Evidence from the issue (reproducible tests):
- Main session responds "PINECONE" when asked about hook content. Subagent says
  "No hook content visible."
- Main session can quote exact Red Flags table rows. Subagent cannot see the table.
- Subagent given identical TDD task without discipline prompt: skips TDD, writes
  implementation first, rationalizes "this is a trivial function."
- Same task WITH discipline prompt: writes tests first, follows Red-Green-Refactor.

### 4. Silent Autonomous Behavior (No Consent)

**Issue #991**: `subagent-driven-development` auto-creates a git worktree without
asking the user. Filed at Jesse Vincent's own request after he agreed this was wrong.
> "User asks to implement a plan → skill invokes EnterWorktree without asking →
> all work happens in isolated worktree → user has to discover and clean up afterward."

**Issue #992**: `executing-plans` SKILL.md contained the instruction "If subagents
are available, use superpowers:subagent-driven-development instead of this skill"
— causing the AI to silently switch strategies when the user had explicitly chosen
executing-plans and saved that decision to memory. "User noticed and called it out —
trust damaged."

### 5. Workflow Is Too Heavyweight for Small Tasks

Richard Porter explicitly:
> "For single-file changes, quick bug fixes, or small refactors, the brainstorm-
> plan-execute cycle adds overhead without proportional benefit."

Feature request **Issue #951**: A user wants a CLI switch to enable/disable
SuperPowers dynamically ("frequent switching between quick edits and complex
planning/TDD workflows").

HN commenter JohnCClarke questioned whether SuperPowers suits experienced
developers, preferring KISS principles.

### 6. Visual Companion Friction

**Issue #892**: Users want a persistent opt-out for the visual companion browser
mode. Current behavior requires responding to the offer every session, which is
a "big speed bump."

> "Generating HTML is also slower than generating text."

DevelopersIO reviewer:
> "Switching between CLI and browser is a bit cumbersome."

**Issue #893**: On Windows, the brainstorm server leaves child processes running
after the session ends.

**Issue #950**: Server serves macOS resource fork dotfiles (._filename) as content.

**Issue #1014** (security): Brainstorm WebSocket server accepts connections from
any origin without validating the `Origin` header. A malicious webpage could
connect while a brainstorm session is active and inject arbitrary content into
Claude's event stream via the events file. Severity rated medium.

### 7. Startup Performance

**Issue #515**: Every time Claude initializes, SuperPowers performs a `git fetch`.
On slow connections to GitHub: ~3-minute startup penalty.

User: "Just do git fetch every day one time, not every time claude init."

### 8. Brainstorming Ignores CLAUDE.md Output Paths

**Issue #939**: The brainstorming skill hardcodes `docs/superpowers/specs/` as the
output path. Even when CLAUDE.md defines a different location, the skill's concrete
path wins. Claude's own diagnosis:

> "The parenthetical '(User preferences for spec location override this default)'
> is easy to gloss over because it's visually subordinate to the concrete path above
> it. It says 'user preferences' which is vague — I didn't connect it to CLAUDE.md's
> output paths table."

### 9. Context Compression Bug

**Issue #968**: During context compression, the system rewrites the entire
compressed context into the chat instead of updating existing context, causing
repeated duplication. This increases token usage and clutters chat history.

### 10. Brainstorming Not Channel-Aware

**Issue #923**: When Claude Code is started with `--channels` (Telegram/Discord
integration), brainstorming skill questions are only printed to the terminal. The
user in Telegram sees the bot go silent. The brainstorm back-and-forth is completely
broken for remote/headless sessions.

### 11. Worktree UX Gaps

**Issue #971**: After brainstorming in a worktree, the spec is committed and the
path is worktree-relative. User's IDE is open on the main repo. Result: they can't
find the file in changed files (it's already committed) and can't navigate to it by
path. The review gate — the most important human checkpoint — is functionally broken.

**Issue #999**: Cleanup sequence in `finishing-a-development-branch` Option 1 fails
when run from inside a worktree: tries to delete a branch while it's still checked
out, then warns about "discarding work" on already-merged commits.

### 12. Plan File Write Failures

**Issue #1042**: When using `writing-plans`, consecutive Write tool calls fail with
"missing required parameter 'file_path'" error after the first succeeds. This forces
a workaround of outputting content to stdout for manual copy-paste. Root cause:
skill system detects file paths in the skill markdown and injects empty Write calls.

### 13. Plugin Discovery/Loading Failures

**Issue #653** and **#643**: After a Claude Code update (v4.3.1), SuperPowers was
no longer recognized in the marketplace. On existing installs, skills stopped loading
and the SessionStart hook stopped firing. On fresh installs, the plugin reported
"not recognized" despite files existing on disk.

**Issue #151**: Skills stopped being auto-discovered despite valid SKILL.md files
and correct frontmatter.

### 14. Duplicate Task Creation

**Issue #1036**: Skills that create tasks via TaskCreate don't check for existing
identical tasks. On context compression or skill re-invocation, the same tasks are
created again, cluttering the task list.

### 15. Hardcoded Developer Paths

Multiple issues (#866, #917): SKILL.md files contained hardcoded paths like
`/Users/jesse/...`. These appeared in user-facing messages and broke when the
plugin ran on any other machine.

### 16. Claude Rationalizes Skipping Skills

Multiple sources confirm this failure mode: Claude actively finds reasons to skip
applying skills even when it should. The Red Flags table in using-superpowers was
added specifically to counter this, but it doesn't reach subagents (Issue #237).

From HN: "Claude is really good at rationalizing why it doesn't make sense to use
a given skill."

---

## What Users Want (Feature Requests)

### High-Priority Requests

1. **Opt-out / on-off switch** — Persistent disable for visual companion; global
   enable/disable toggle for the whole plugin without manual symlink management.
   (Issues #892, #951)

2. **Intent-level plans instead of code-level plans** — Plans should describe
   what/why/acceptance criteria, not write the actual implementation. Multiple
   community members proposed interface contracts + acceptance criteria as the
   right abstraction. Jesse Vincent acknowledged the problem but hasn't merged
   a fix. (Issue #895)

3. **SubagentStart hook** — Inject using-superpowers discipline context into
   subagents so they follow TDD and skill-first behavior. (Issue #237)

4. **Research step in brainstorming** — Add a step between clarifying questions
   and proposing approaches to verify that proposed libraries/APIs actually exist
   and are maintained. Prevents "confidently propose something that doesn't work."
   (Issue #983)

5. **Plan session handoff** — `/create_handoff` and `/resume_plan` commands to
   preserve plan state across sessions. (Issue #931)

6. **Canonical learnings section** — A documented place for project/team-specific
   knowledge that persists across sessions and accumulates verified facts without
   polluting skill files. (Issue #907)

7. **Post-mortem analysis skill** — A skill for analyzing production failures using
   structured frameworks like the 4M method. (Issues #969, #1008)

8. **Writing-skills YAML quoting guidance** — Multiple issues about SKILL.md
   frontmatter: description values need quoting when they contain special characters,
   and the writing-skills skill gave incorrect guidance. (Issues #955, #979)

9. **Plan iteration skill** — A skill for refining and re-executing plans after
   the initial execution reveals gaps. (Issues #921, #943)

10. **Research-first brainstorming** — Brainstorming should check for existing
    solutions before proposing approaches, not just reason from training data.

### Cross-Platform / Multi-Harness Requests

- Codex CLI: subagent support (Issues #984, #956), worktree compatibility (#901)
- Trae IDE: native support files (Issue #947)
- Kimi Code CLI: harness support (Issue #1043)
- Gemini CLI: subagent support mapping fixes (Issue #941)
- OpenCode: plugin auto-update (Issue #942), multiple system message compatibility (#894)
- Windows/Cursor: SessionStart hook via run-hook.cmd (Issues #871, #912)
- Hermes Agent: installation guide (Issue #881)

### Quality/Architecture Requests

- **Blind review skill**: Final review against spec only, without seeing the
  implementation, to catch spec compliance issues. (Issue #865)
- **Retrospective skill**: End-of-session improvement capture. (Issue #864)
- **Capability-first skill design**: Multiple contributors argue skills should
  teach engineering judgment, not SOPs. One commenter: "teach the model how to
  think and decide like an engineer, not just how to follow a SOP." (Issue #895 thread)
- **Worktree-first isolation by default**: With delta analysis for parallel session
  safety. (Issue #997)
- **Skill-aware task deduplication**: Before TaskCreate, check TaskList for
  existing matches. (Issue #1036)
- **Share hooks with worktrees via symlink**: So hooks defined in the main repo
  are available in all worktrees. (Issue #965)

---

## Common Themes and Patterns

### Theme 1: The Workflow Adds Real Value for Complex Work

There is strong consensus that SuperPowers meaningfully improves outcomes for
multi-file features, architectural decisions, and anything needing comprehensive
test coverage. The brainstorm → plan → implement cadence prevents the most common
failure mode of AI coding tools: premature implementation before requirements are
understood.

### Theme 2: It's Overkill for Simple Tasks and Users Know It

No reviewer claims you should use SuperPowers for everything. The overhead is
unjustified for single-file changes or quick bug fixes. The lack of a simple
toggle between "structured mode" and "quick mode" is a genuine friction point
with multiple feature requests.

### Theme 3: Token Cost is a Real Concern

The 22k token baseline overhead, combined with detailed planning that writes
implementation code, adds up. Users on subscription plans (especially Max) report
hitting limits faster. Several users report switching back to plain Claude Code
Plan mode for cost reasons.

### Theme 4: Silent Autonomous Decisions Break Trust

Multiple issues document SuperPowers making decisions without consent: auto-creating
worktrees, silently switching execution strategies, committing files before review.
Users notice and file bugs. Jesse Vincent himself acknowledged and filed #991.

### Theme 5: Platform Fragmentation

The project now targets Claude Code, Cursor, OpenCode, Codex, Gemini CLI, Kimi Code,
Trae IDE, and Hermes Agent. The Windows/Cursor SessionStart hook alone has been
reported 29 times (mentioned in the issue template warning). Platform-specific bugs
are a significant and growing maintenance burden.

### Theme 6: Skeptics Question the Fundamentals

HN commenters raised foundational objections at the original announcement:
- "Seems cute, but ultimately not very valuable without benchmarks." (jackblemming)
- "This style of prompting with capitalized keywords is already dated." (tcdent)
- "I don't see any code. Where are the examples of use on real code?" (JaggerFoo)
- "LLM-generated skill documentation lacks real explanatory value since models
  already understand concepts in their training data." (hoechst)

These were not addressed by the reviewer community. The plugin's growth (135k stars)
suggests practical users are less concerned about theoretical objections, but the
absence of rigorous benchmarks remains a gap.

### Theme 7: The Planning Abstraction Level Is Actively Contested

Issue #895 is the most substantive open debate: should plans contain implementation
code or only intent + contracts? The community is split. Jesse Vincent believes plans
need to be prescriptive enough for weaker models. Several power users argue the
current design actively harms stronger models by preventing engineering judgment.
No resolution yet.

---

## What This Means for fakoli-flow

### Opportunities to Do Differently

1. **Progressive context loading** — Don't load all skills at startup. Load metadata
   only (~100 tokens/skill) and expand on demand. SuperPowers loads 22k tokens at
   baseline; fakoli-flow should aim for <2k.

2. **Intent-level plans, not code-level plans** — The write-plans → execute-plans
   loop should produce contracts + acceptance criteria + constraints, not function
   bodies. Let the executor exercise judgment. This is the highest-signal unresolved
   complaint in the SuperPowers issue tracker.

3. **Explicit consent before autonomous actions** — Never auto-create worktrees,
   never silently switch execution strategies, never commit files without showing
   the path and asking. Present choices, record the user's decision, respect it.

4. **Subagent context propagation** — Ensure discipline context reaches subagents.
   The PINECONE test in Issue #237 is a concrete reproduction recipe. fakoli-flow
   should verify this works via SubagentStart hook injection.

5. **Quick mode / no-overhead path** — Small tasks should be completable without
   triggering the full workflow. A simple flag, env var, or CLAUDE.md setting should
   control when the structured workflow activates vs. when the agent works directly.

6. **Channel-aware skill output** — Any skill that asks interactive questions must
   route through the active channel (Telegram, Discord, etc.) rather than printing
   to terminal. SuperPowers brainstorming is broken for headless use.

7. **Reliable file paths** — Never hardcode developer-specific paths. Always use
   project-relative or configurable paths. Respect CLAUDE.md output path configuration
   explicitly, not as a parenthetical afterthought.

8. **Context-safe brainstorm storage** — Store brainstorm sessions outside the
   working tree by default. Default to `~/.local/share/` or XDG-compliant paths,
   not in the repo.

9. **Validation of approach before planning** — Add a research/verification step
   that checks whether proposed libraries/APIs exist and are current before writing
   a plan that depends on them.

10. **Benchmarks or evals** — The single most credible criticism of SuperPowers is
    the absence of rigorous comparison data. Even simple before/after measurements
    (test pass rates, task completion times, rework frequency) would distinguish
    fakoli-flow from the field.

### What SuperPowers Gets Right That fakoli-flow Should Match

- One-question-at-a-time brainstorming (not 10 questions at once)
- Producing an editable markdown spec the user can open in their editor
- Adversarial self-review of the spec before presenting it to the user
- Explicit options + tradeoffs before choosing an approach
- TDD enforcement as a hard gate, not a soft suggestion
- Subagent-driven parallel execution with code review at each task boundary
- Skill authoring: users can write and contribute their own skills

---

## Sources

- GitHub repository: https://github.com/obra/superpowers
- HN rave review discussion: https://news.ycombinator.com/item?id=47623101
- HN original announcement: https://news.ycombinator.com/item?id=45547344
- Evan Schwartz rave review: https://emschwartz.me/a-rave-review-of-superpowers-for-claude-code/
- Jesse Vincent original post: https://blog.fsck.com/2025/10/09/superpowers/
- Jesse Vincent Superpowers 5 post: https://blog.fsck.com/2026/03/09/superpowers-5/
- Simon Willison's notes: https://simonwillison.net/2025/Oct/10/superpowers/
- Trevor Lasn review: https://www.trevorlasn.com/blog/superpowers-claude-code-skills
- Richard Porter review: https://richardporter.dev/blog/superpowers-plugin-claude-code-big-features
- DevelopersIO brainstorming experience: https://dev.classmethod.jp/en/articles/2026-03-17-superpowers-brainstorming/
- Claude Plugin Hub listing: https://www.claudepluginhub.com/plugins/obra-superpowers-2
- Anthropic official listing: https://claude.com/plugins/superpowers
- Geeky Gadgets review: https://www.geeky-gadgets.com/claude-code-superpowers-plugin/
- GitHub issues directly cited:
  - #190 (token preloading): https://github.com/obra/superpowers/issues/190
  - #237 (subagent context): https://github.com/obra/superpowers/issues/237
  - #515 (git fetch on startup): https://github.com/obra/superpowers/issues/515
  - #750 (token consumption Opencode): https://github.com/obra/superpowers/issues/750
  - #895 (plans over-specify): https://github.com/obra/superpowers/issues/895
  - #892 (visual companion opt-out): https://github.com/obra/superpowers/issues/892
  - #907 (learnings section): https://github.com/obra/superpowers/issues/907
  - #923 (channels not forwarded): https://github.com/obra/superpowers/issues/923
  - #939 (CLAUDE.md output path ignored): https://github.com/obra/superpowers/issues/939
  - #953 (100% tokens in 5 min): https://github.com/obra/superpowers/issues/953
  - #968 (context compression duplication): https://github.com/obra/superpowers/issues/968
  - #971 (worktree spec review UX): https://github.com/obra/superpowers/issues/971
  - #975 (brainstorm session storage): https://github.com/obra/superpowers/issues/975
  - #983 (research step in brainstorming): https://github.com/obra/superpowers/issues/983
  - #991 (worktree auto-created without consent): https://github.com/obra/superpowers/issues/991
  - #992 (silent strategy switch): https://github.com/obra/superpowers/issues/992
  - #999 (worktree cleanup bugs): https://github.com/obra/superpowers/issues/999
  - #1014 (WebSocket security): https://github.com/obra/superpowers/issues/1014
  - #1036 (duplicate tasks): https://github.com/obra/superpowers/issues/1036
  - #1042 (Write tool failures): https://github.com/obra/superpowers/issues/1042
  - #1051 (parent blocked by child approval): https://github.com/obra/superpowers/issues/1051
