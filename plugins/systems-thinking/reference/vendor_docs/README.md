# Vendor Docs

Vendor documentation, pricing notes, quotas, limitations, region availability, and SLA details.

## What goes here

- Service quotas and hard limits
- Pricing mechanics and cost gotchas
- Region availability and feature gaps
- SLA details and support tier differences
- Implementation caveats buried in vendor docs

## How agents and skills use this folder

- **`doc-indexer`** maps the structure of files here and flags high-value sections.
- **`doc-reader`** extracts technical claims, limits, and dependencies.
- **`caveat-extractor`** finds buried traps — soft limits, undocumented behaviors, deprecation signals.
- **`cost-capacity-analyst`** identifies pricing mechanics and scaling constraints.
- **`complexity-mapper`** and **`context-sharding`** skills pull from this folder during analysis workflows.

## File guidelines

- Markdown preferred. Export or convert vendor PDFs to Markdown before adding.
- One vendor or service per file.
- Note the date of the source documentation — vendor docs go stale fast.
- Preserve exact numbers for quotas, limits, and pricing rather than paraphrasing.

## Example filenames

- `aws-transit-gateway-quotas-2025-03.md`
- `azure-expressroute-pricing-2025-02.md`
- `gcp-cloud-interconnect-sla-2025-01.md`
