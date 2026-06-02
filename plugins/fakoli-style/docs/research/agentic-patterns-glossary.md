# Agentic Architecture Patterns — Research Glossary

> **Status: research reference, not governance.** This file is hand-authored background
> material. It is **not** part of the principles ledger and is **not** generated from
> `data/principles.json`. It captures an external pattern vocabulary so that the
> patterns Fakoli already practices can be *named and recognized*, not adopted.
>
> **Provenance.** The vocabulary below is distilled from the Google Cloud
> architecture guidance on agentic systems (see [Sources](#sources)). Fakoli was
> not designed from these documents — they are used here as an independent,
> well-articulated taxonomy that happens to name forces Fakoli arrived at on its
> own. Treat this as a dictionary, not a blueprint.

---

## How to read this glossary

Each entry gives the pattern's **name**, **what it is**, **when it fits**, and its
**main cost or failure mode**. The companion document
[`architecture-view.md`](./architecture-view.md) maps these entries onto the actual
Fakoli plugins (`fakoli-state`, `fakoli-flow`, `fakoli-crew`) and the governing
principles in the ledger.

A useful upstream framing from the source material: *the choice of pattern is driven
by four properties of the work* — **task complexity, latency tolerance, cost budget,
and required human involvement.** A predictable, single-call task may not need an
agentic pattern at all.

---

## Part 1 — Orchestration design patterns

### Single-agent
One model, one toolset, one system prompt, acting autonomously over multiple steps.
Fits structured multi-step tasks with external tools; simplest to build. Degrades as
tool count grows (wrong-tool selection, latency, non-completion).

### Sequential
A fixed linear pipeline: each stage's output is the next stage's input, with **no model
deciding the order**. Fits stable, repeatable processes (extract → clean → load). Cheap
and low-latency; rigid and hard to adapt or short-circuit.

### Parallel
Independent subtasks run concurrently, then a gather step synthesizes their outputs.
Fits latency reduction or gathering diverse perspectives. Raises peak resource/token
use; the synthesis step needs logic to reconcile conflicting results.

### Loop
A specialized step repeats until a termination condition is met. Fits polling,
monitoring, or repeated refinement. **Primary failure mode: a wrong/missing termination
condition → infinite loop, runaway cost, hangs.**

### Review & critique
A generator produces output; a separate **critic** evaluates it against explicit
criteria and may approve, reject, or send back for revision. Fits work that must be
accurate or constraint-conforming before release (e.g. code that needs a security pass).
Adds at least one extra model call per cycle; revision loops compound latency and cost.

### Iterative refinement
One or more agents loop over a working draft held in session state until it meets a
quality bar or hits a max-iteration ceiling. Fits hard generation tasks (long documents,
multi-part plans, debugging). Each cycle adds latency/cost; needs carefully designed exit
conditions.

### Coordinator (a.k.a. router / orchestrator)
A central agent uses **model reasoning** to decompose a request and dynamically route
sub-tasks to specialists. Distinguished from Parallel by the routing being *learned at
runtime*, not hardcoded. Flexible across varied inputs; costs more model calls, tokens,
and latency than a single agent.

### Hierarchical task decomposition
A root agent recursively decomposes a problem across layers of sub-agents until tasks
reach worker level. A Coordinator applied at depth. Fits ambiguous, open-ended problems
(research → analysis → synthesis). Higher-quality results; considerable architectural
complexity and many model calls.

### Swarm
A group of peer agents that can all communicate with each other, sharing findings and
critiques, with **no central supervisor**. Any agent can hand off or finalize. Fits
debate-style problems benefiting from many perspectives. The most complex and costly
pattern; without a coordinator it risks unproductive loops or failure to converge.

### ReAct (reason → act → observe)
A single agent iterates: *Thought* (reason about next step) → *Action* (pick a tool or
answer) → *Observation* (record the result), until a stop condition. Fits dynamic tasks
needing continuous planning; the thought transcript aids debugging. Higher end-to-end
latency; quality bounded by the model's reasoning; errors propagate.

### Human-in-the-loop (HITL)
The system pauses at predefined checkpoints to await human approval, correction, or
input before continuing. Fits high-stakes, subjective, or safety-critical decisions.
Adds the complexity of building and maintaining the human-interaction surface.

### Custom logic
Hand-written control flow (conditionals, branches) mixing rules with model reasoning for
workflows that fit no standard template. Maximum flexibility; maximum
design/debug/maintenance burden.

---

## Part 2 — Multi-agent system concepts

### Specialized agent roles
A reference decomposition of responsibilities: a **coordinator** that routes; **specialist
sub-agents** for domain tasks; a **quality evaluator** that judges outputs; a **prompt
enhancer** that refines inputs on failure; a **response generator** that produces the final,
grounded answer.

### Agent-to-agent communication (A2A)
A protocol for interoperability between agents regardless of language or runtime. The
key idea for design purposes: **inter-agent messages are a typed, authenticated contract**,
not free-form text. (In a networked deployment this means HTTPS/TLS + OAuth/OIDC; the
*design intent* is "schema'd, authenticated handoffs.")

### Tool standardization (MCP)
A standard client/server contract for agent→tool calls (databases, files, APIs). Tool
descriptions must state purpose, arguments, and usage; tool access is authorized and
monitored.

### State & memory / context engineering
Agents must carry **sufficient context to track multi-turn interactions and session
parameters** — but no more. Managing what flows between agents (documentation,
preferences, history, **compression**) is a first-class design activity, not an
afterthought.

### Evaluation
Continuously assess both the **output** *and* the **trajectory** (the steps taken to reach
it). Human reviewers approve/reject and give corrective guidance.

### Observability
The system should make visible **every action an agent takes — reasoning, tool selection,
and execution path** — via structured logging and tracing, so failures in complex
workflows can be diagnosed.

### Error handling
Logging, exception handling, and retries at the agent level; design for tolerating
agent-level failure (decentralization where feasible); graceful handling of off-topic or
ambiguous inputs ("no-match" logic).

### Least-privilege access
Grant each agent **only** the permissions it needs to do its task and to talk to its
tools and peers. Pair carefully-scoped autonomy with human oversight and observability.

### Input/output inspection
An inspection point that screens model **inputs and outputs** for prompt injection and
harmful content — a barrier between untrusted content and the agents acting on it.

---

## Part 3 — Isolation & trust-boundary concepts

> These come from the networking-patterns guidance. They are written for *networked*
> deployments (VPCs, load balancers, service identities). For an **in-process** system
> like Fakoli they apply as *design intent translated to the local substrate*, not as
> literal infrastructure.

### Trust boundary
An explicit line across which data or control changes trust level. Crossing it should be
mediated and inspected, never implicit.

### Least-privilege / service identity
Each component runs with the narrowest identity and permission set sufficient for its
job (network analog: per-service IAM roles; in-process analog: per-agent tool allow-lists).

### Default-deny egress
Deny outbound actions by default; allow only explicitly enumerated flows. Prevents
unauthorized side effects and data exfiltration.

### Layered defense (defense in depth)
Independent control layers (network, API perimeter, application/content inspection,
edge) so no single layer is the only thing standing between untrusted input and the
system.

### Persona / responsibility separation
Separate the people (or modules) who own infrastructure and security from those who own
application logic, with a clear boundary between them. (Software analog: a governance
layer distinct from the implementations it governs.)

---

## Sources

- Google Cloud — *Choose a design pattern for your agentic AI system*
- Google Cloud — *Multi-agent AI system* (reference architecture)
- Google Cloud — *Multi-agent system networking and isolation patterns*

These are external references used as a pattern dictionary. Where a pattern here is
something Fakoli already does, it is recorded as an *embodiment* of an existing ledger
principle in [`architecture-view.md`](./architecture-view.md) — not as a new requirement.
