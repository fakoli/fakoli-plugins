---
name: Architecture Risk Review
description: >
  Targeted review of failure modes, hidden dependencies, limits, and operational burden in a
  specific architecture or design. Use this when you need a focused risk assessment without
  running a full complexity mapping — to identify single points of failure, blast radius concerns,
  hidden coupling, and operational survivability gaps. Produces a Hidden Risk Summary with
  dependency risk matrix, compound failure scenarios, and prioritized remediation actions.
  Ask for an "architecture risk review", "failure mode analysis", or "dependency risk assessment"
  to use this workflow.
---

# Architecture Risk Review

## When to Use

Use Architecture Risk Review when:

- You need a focused risk assessment of a specific architecture or design — not a full complexity mapping, but a targeted investigation of what can go wrong.
- An architecture has been proposed or is in production and you want to identify failure modes, hidden dependencies, operational limits, and maintenance burden before they become incidents.
- A change is being proposed to an existing architecture and you need to understand the risk surface of the change.
- You want to validate that an architecture can survive its stated failure scenarios and degrade gracefully under load.

Do **not** use Architecture Risk Review when:

- You need a broad complexity analysis covering cost, capacity, and implementation concerns beyond architecture. Use `complexity-mapper` for that.
- The architecture documentation is so extensive that it needs sharding before analysis. Run `context-sharding` first.
- There is no architecture to review — only aspirational goals or early-stage ideas. Recommend solidifying the design first.

## Inputs Required

| Input               | Required | Description                                                                                                                                                                                             |
| ------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Design artifacts    | Yes      | Architecture diagrams, system design documents, infrastructure-as-code, service definitions, API contracts, data flow diagrams. The more concrete the artifacts, the more specific the risk assessment. |
| Architecture docs   | Yes      | Technical documentation describing the system: component responsibilities, communication patterns, data storage strategy, deployment model, scaling approach.                                           |
| Caveats             | No       | Known limitations, quotas, or constraints already identified. If provided, the review will validate and extend them rather than rediscover them.                                                        |
| Dependency maps     | No       | Pre-existing dependency maps or service catalogs. If not provided, the review will construct them from the design artifacts.                                                                            |
| Operational context | No       | Current operational reality: incident history, monitoring coverage, on-call structure, deployment frequency, rollback capabilities. Significantly improves risk severity calibration.                   |

## Process Steps

### Step 1: Invoke doc-indexer on Architecture Documents

Before running the doc-indexer, check these reference directories for supplementary material:

- `plugins/systems-thinking/reference/previous_designs/` — prior architecture work that may reveal historical risk patterns or recurring failure modes relevant to this review.
- `plugins/systems-thinking/reference/vendor_docs/` — vendor documentation covering known limitations, quotas, or service constraints relevant to the architecture under review.

Include any relevant reference materials as additional input to the doc-indexer.

Run the `doc-indexer` agent on all provided architecture documents to produce:

- A component inventory: every named service, database, queue, cache, API, and external dependency.
- A communication map: how components talk to each other (sync/async, protocols, data formats).
- A boundary map: where the system's boundaries are (network boundaries, trust boundaries, organizational boundaries, cloud region/zone boundaries).
- An identification of undocumented areas: components mentioned but not described, integrations implied but not detailed, failure scenarios alluded to but not specified.

Undocumented areas are themselves a risk signal. Log them for inclusion in the final output.

### Step 1.5: Conditionally Invoke web-researcher for External Sources

If the architecture depends on external services, cloud platforms, or vendor products whose documentation is not available locally:

1. Invoke the `web-researcher` agent to discover relevant vendor documentation (service quotas, SLAs, known issues, pricing).
2. Present the Source Manifest to the user for review before proceeding.
3. Feed approved sources into doc-indexer for structural mapping.

**Skip this step** if all vendor documentation is already available in `plugins/systems-thinking/reference/vendor_docs/` or provided by the user.

### Step 1.75: Invoke extraction-planner for Dispatch Planning

If the doc-indexer output identifies more than 5 sections for extraction, run the `extraction-planner` agent to produce a Dispatch Plan. This determines how many caveat-extractors and dependency-mappers to spawn and what scoped instructions each receives.

**Skip this step** if the doc-indexer identifies ≤5 architecture-relevant sections. Use a single caveat-extractor and single architecture-dependency-mapper.

### Step 2: Run caveat-extractor on Architecture-Relevant Sections

Following the Dispatch Plan (or default single-extractor if Step 1.75 was skipped), run the `caveat-extractor` agent(s) on sections identified by the doc-indexer as architecture-relevant:

**Extraction targets:**

- **Hard limits**: Connection pools, file descriptor limits, DNS TTLs, certificate expiration, API rate limits, storage quotas, message size limits, timeout configurations.
- **Soft limits that harden under stress**: Autoscaling lag, cold start penalties, connection draining timeouts, retry storm thresholds, circuit breaker configurations.
- **Deprecation and drift risks**: Components on deprecated APIs, libraries approaching end-of-life, infrastructure running unsupported versions, configurations that rely on undocumented behavior.
- **Operational burden**: Components requiring manual intervention, scheduled maintenance windows, manual failover procedures, configuration that must be kept in sync across services.
- **Failure propagation paths**: How a failure in one component cascades. Look for missing circuit breakers, unbounded retry loops, synchronous chains without timeouts, shared failure domains.

For each caveat extracted, require:

- The specific limit or risk.
- The source in the documentation.
- The conditions under which it becomes a problem.
- A severity assessment: Critical (system down), High (degraded service), Medium (increased operational burden), Low (technical debt).

### Step 3: Run architecture-dependency-mapper on Design Artifacts

Run the `architecture-dependency-mapper` agent on the design artifacts to produce a comprehensive dependency analysis:

**For each dependency, map:**

- **Type**: Runtime (required for operation), Build-time (required for deployment), Data (data flows through it), Configuration (settings sourced from it).
- **Direction**: Upstream (we depend on it), Downstream (it depends on us), Bidirectional.
- **Ownership**: Internal (our team), Internal-other (another team in our org), External-vendor (third-party SaaS), External-OSS (open source, community maintained).
- **SLA**: Documented availability target. If no SLA exists, flag this.
- **Failure mode**: What happens when this dependency is unavailable? (Graceful degradation, partial outage, full outage, data loss, silent corruption.)
- **Blast radius**: What else breaks when this dependency fails?
- **Recovery**: How is this dependency restored? (Auto-recovery, manual intervention, redeployment, vendor ticket.)

**Specific patterns to flag:**

- Single points of failure: Components with no redundancy whose failure causes system-wide impact.
- Hidden coupling: Components that appear independent but share underlying infrastructure (same database, same network path, same DNS resolver, same certificate authority).
- Transitive dependencies: A depends on B depends on C, where C's failure mode is not accounted for in A's design.
- Ownership gaps: Dependencies where no team has clear operational responsibility.
- Clock and ordering dependencies: Systems that assume synchronized clocks, ordered delivery, or exactly-once semantics without guaranteeing them.

### Step 4: Invoke synthesis-brief-writer for Hidden Risk Summary

Pass the caveat-extractor output and the dependency map to the `synthesis-brief-writer` agent with instructions to produce a **Hidden Risk Summary focused on architectural risks**.

The synthesis must:

1. **Correlate caveats with dependencies**: A rate limit on Service X is a footnote in isolation but becomes critical when Service Y has a retry-on-failure pattern against Service X.
2. **Identify compound failures**: Scenarios where two individually manageable risks combine to produce a severe outcome. Example: autoscaling lag + connection pool exhaustion = cascading failure.
3. **Assess operational survivability**: For each identified risk, can the current operational posture (monitoring, alerting, runbooks, on-call) detect and respond to it before customer impact?
4. **Rate severity** using a consistent scale:
   - **Critical**: System-wide outage or data loss. Requires immediate architectural remediation.
   - **High**: Significant service degradation. Requires remediation before next major release or scaling event.
   - **Medium**: Increased operational burden or localized degradation. Should be addressed in normal planning.
   - **Low**: Technical debt or minor resilience gap. Track and address opportunistically.

### Step 5: Present Findings with Severity Ratings and Source Anchors

Cross-reference findings against any prior risk summaries or architecture review examples in `plugins/systems-thinking/reference/examples/` to ensure consistent severity calibration and output format.

Deliver the Hidden Risk Summary with:

- **Executive summary**: 3-5 sentences covering the architecture's overall risk posture and the most critical findings.
- **Risk inventory**: Every identified risk with severity, evidence, and recommended action.
- **Dependency risk matrix**: Visual summary of which dependencies pose the highest risk.
- **Source anchors**: Every finding linked to specific document sections, diagram elements, or code locations.
- **Recommended actions**: Prioritized list of what to fix, investigate, or monitor, ordered by severity and effort.

## Output Format

The output is a **Hidden Risk Summary with architectural focus** conforming to the output contract:

```
## Architecture Risk Review — Hidden Risk Summary

### Executive Summary
[3-5 sentences: overall risk posture, most critical findings, recommendation urgency]

### Risk Inventory

#### Critical Risks

##### [Risk Name]
- **Description**: [What the risk is]
- **Trigger**: [Conditions that cause it to materialize]
- **Impact**: [What breaks and how badly]
- **Evidence**: [Specific findings with source anchors]
- **Compound factors**: [Other risks that amplify this one]
- **Current detectability**: [Can monitoring/alerting catch this before customer impact? Yes/Partial/No]
- **Recommended action**: [Specific remediation with effort estimate]

#### High Risks
[Same structure as Critical]

#### Medium Risks
[Same structure, abbreviated — description, trigger, recommended action]

#### Low Risks
[Listed as bullet points with brief descriptions]

### Dependency Risk Matrix

| Dependency | Type | Ownership | SLA | Failure Mode | Blast Radius | Severity |
|---|---|---|---|---|---|---|
| [Name] | [Runtime/Build/Data/Config] | [Internal/Vendor/OSS] | [SLA or "Undocumented"] | [Degradation/Outage/Data loss] | [Scope] | [C/H/M/L] |

### Undocumented Areas
- [Area]: [What is missing and why it matters for risk assessment]

### Compound Failure Scenarios
| Scenario | Risks Involved | Combined Impact | Likelihood |
|---|---|---|---|
| [Scenario name] | [Risk A + Risk B] | [What happens] | [H/M/L] |

### Recommended Actions (Priority Order)
| Priority | Action | Addresses Risk(s) | Effort | Owner |
|---|---|---|---|---|
| 1 | [Action] | [Risk name(s)] | [Hours/Days/Weeks] | [Suggested] |
| 2 | [Action] | [Risk name(s)] | [Effort] | [Suggested] |

### Source Index
[Map of finding IDs to specific document sections, diagram elements, or code locations]
```

## Failure Modes and Caution Points

| Failure Mode                                         | Signal                                                                                                                                                                   | Response                                                                                                                                                                                                                                                  |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Architecture documentation incomplete                | doc-indexer identifies multiple undocumented components or integrations; caveat-extractor returns sparse results for key components                                      | Proceed with available information but prominently flag documentation gaps in the output. List undocumented areas as risks in their own right. Recommend documentation remediation as a high-priority action.                                             |
| Design too abstract for concrete risk identification | Artifacts describe high-level intent ("microservices architecture with event-driven communication") without specifying technologies, configurations, or failure handling | Downgrade the review to a risk questionnaire: list the questions that must be answered before a concrete risk assessment is possible. Present these as the primary output rather than producing a speculative risk inventory.                             |
| Missing operational context                          | No incident history, monitoring coverage, or on-call information provided                                                                                                | Proceed but lower confidence on detectability assessments. Note in every detectability field that the assessment is based on architectural inference, not operational data. Recommend providing operational context for a higher-fidelity review.         |
| Single architecture perspective                      | All documentation comes from one team or one role (e.g., only the development team, no ops or security perspective)                                                      | Flag the limited perspective in the executive summary. Recommend soliciting input from operations, security, and any teams that own upstream or downstream dependencies.                                                                                  |
| Review surface too large                             | Architecture spans more than 15 distinct services or components                                                                                                          | Recommend scoping the review to a specific subsystem or failure domain. Alternatively, run `context-sharding` to split the architecture into reviewable segments, then run architecture-risk-review on each segment with a final cross-segment synthesis. |
| Known caveats provided but outdated                  | User provides caveats that reference deprecated configurations or resolved issues                                                                                        | Validate provided caveats against current documentation. Flag any that appear outdated. Do not carry stale caveats into the risk summary without verification.                                                                                            |
