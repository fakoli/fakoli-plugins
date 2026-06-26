# Output Contracts

This document defines the five standard output formats used by the systems-thinking-plugin. Every synthesis agent and skill should produce output that conforms to one of these contracts. Extraction agents produce Context Packets; synthesis agents produce one of the other four.

The contracts exist so that outputs are predictable, composable, and useful in downstream workflows (design reviews, stakeholder conversations, follow-up analysis).

---

## 1. Hidden Risk Summary

Surface risks that are not obvious from a surface reading of the source material.

### Required sections

| Section              | Purpose                                                                                    |
| -------------------- | ------------------------------------------------------------------------------------------ |
| Scope Reviewed       | What was examined and what was explicitly out of scope                                     |
| Top Hidden Risks     | Risks that are non-obvious, buried, or easily overlooked                                   |
| Likely Impact Areas  | Where each risk is most likely to cause problems (cost, timeline, operations, reliability) |
| Assumptions          | What the analysis assumed to be true that was not verified                                 |
| Unresolved Questions | Open items that could not be answered from available material                              |
| Source Anchors       | File, section, or page reference for each finding                                          |

### Example structure

```markdown
## Scope Reviewed

Reviewed vendor networking documentation v3.2, sections 1-8 and appendix B.

## Top Hidden Risks

1. Regional failover requires manual DNS cutover — not automated.
   - **Source:** vendor-networking-v3.2.pdf, section 4.3, paragraph 2

## Likely Impact Areas

- Operational burden during outages (Risk 1)

## Assumptions

- Vendor documentation is current as of review date.

## Unresolved Questions

- What is the actual failover time under load?

## Source Anchors

- vendor-networking-v3.2.pdf, sections 4.3, 6.1, appendix B
```

---

## 2. Complexity Heat Map

Identify areas of high implementation or operational complexity and rate them.

### Required sections

| Section         | Purpose                                                                 |
| --------------- | ----------------------------------------------------------------------- |
| Complexity Area | A named area where complexity concentrates                              |
| Why It Matters  | Concrete impact if this complexity is underestimated                    |
| Severity        | High / Medium / Low rating for implementation or operational difficulty |
| Confidence      | How confident the assessment is, given available evidence               |
| Source Anchors  | File, section, or page reference supporting the assessment              |

### Example structure

```markdown
## Complexity Heat Map

| Area                        | Why It Matters                                     | Severity | Confidence | Source                     |
| --------------------------- | -------------------------------------------------- | -------- | ---------- | -------------------------- |
| Cross-region routing policy | Requires coordinating 3 teams and 2 vendor configs | High     | Medium     | design-doc.md, section 3   |
| Certificate rotation        | Undocumented dependency on legacy PKI              | Medium   | Low        | ops-runbook.md, appendix A |
```

---

## 3. Decision Brief

Package findings for engineers, managers, or review bodies who need to make or approve a decision.

### Required sections

| Section                 | Purpose                                                                      |
| ----------------------- | ---------------------------------------------------------------------------- |
| Decision Under Review   | What decision is being evaluated                                             |
| Options Considered      | The alternatives that were analyzed                                          |
| Evidence Summary        | Key facts extracted from source material, with anchors                       |
| Inferred Concerns       | Concerns the analyst inferred but that were not stated explicitly in sources |
| Top Risks               | The most significant risks to the preferred option                           |
| Recommended Next Checks | Concrete follow-up actions to reduce uncertainty                             |
| Unresolved Questions    | Items that remain open and could change the recommendation                   |

### Example structure

```markdown
## Decision Under Review

Whether to use vendor X or vendor Y for cross-cloud connectivity.

## Options Considered

1. Vendor X managed interconnect
2. Vendor Y SD-WAN overlay
3. Self-managed IPsec tunnels

## Evidence Summary

- Vendor X supports 10 Gbps but has a 500-route soft limit. (vendor-x-docs.pdf, p.14)

## Inferred Concerns

- Vendor X's pricing model may not scale linearly beyond 3 regions.

## Top Risks

1. Route limit exceeded during migration (High)

## Recommended Next Checks

- Request Vendor X's route-limit enforcement behavior in writing.

## Unresolved Questions

- Does Vendor Y support BGP communities for traffic engineering?
```

---

## 4. Pattern Remix Draft

Adapt prior proven work to a new but related problem.

### Required sections

| Section                 | Purpose                                                             |
| ----------------------- | ------------------------------------------------------------------- |
| Target Outcome          | What the new design or plan needs to achieve                        |
| Reusable Prior Patterns | Which elements from prior work apply and why                        |
| Constraints             | Hard constraints on the new problem that differ from the prior work |
| Proposed Approach       | The adapted design or plan                                          |
| Implementation Steps    | Ordered steps to execute the approach                               |
| Known Risks             | Risks introduced by reuse, adaptation gaps, or new constraints      |

### Example structure

```markdown
## Target Outcome

Extend the hub-spoke network to a third cloud provider with minimal changes to the existing hub.

## Reusable Prior Patterns

- Hub firewall policy structure from the AWS-GCP interconnect project.
- Terraform module layout from infra-modules/networking/hub-spoke/.

## Constraints

- Third provider does not support BGP with the hub appliance natively.

## Proposed Approach

Use a transit gateway with static routes as a bridge, then migrate to BGP when provider support lands.

## Implementation Steps

1. Deploy transit gateway in provider C.
2. ...

## Known Risks

- Static routes will not failover automatically.
```

---

## 5. Context Packet

The standard output of extraction agents. Context Packets are consumed by synthesis agents to produce the other four contract types.

### Required sections

| Section                      | Purpose                                                         |
| ---------------------------- | --------------------------------------------------------------- |
| Source Name                  | The document, file, or system that was read                     |
| Section / Scope Reviewed     | Which parts were covered                                        |
| Extracted Findings           | Facts, claims, constraints, and details pulled from the source  |
| Caveats                      | Limitations, contradictions, or ambiguities found in the source |
| Confidence / Ambiguity Notes | How complete and trustworthy the extraction is                  |
| Source Anchors               | File, section, page, or line references for every finding       |

### Example structure

```markdown
## Source Name

vendor-x-networking-guide-v3.2.pdf

## Section / Scope Reviewed

Sections 4 through 6 (routing, failover, monitoring).

## Extracted Findings

- Maximum of 500 BGP routes per interconnect. (section 4.3)
- Failover relies on BFD with a 3-second detection interval. (section 5.1)

## Caveats

- Section 5.2 references "automatic failover" but the procedure described is manual.

## Confidence / Ambiguity Notes

- High confidence on route limits (explicit quota).
- Low confidence on failover behavior (contradictory statements in sections 5.1 vs 5.2).

## Source Anchors

- vendor-x-networking-guide-v3.2.pdf: sections 4.3, 5.1, 5.2, 6.4
```

---

## Usage notes

- Extraction agents always produce **Context Packets**.
- Synthesis agents consume Context Packets and produce one of the other four formats.
- If an output does not fit any contract cleanly, use the closest match and note deviations at the top.
- Source anchors are required in every contract. If you cannot anchor a finding, mark it as "inferred" or "unanchored" explicitly.
