# CloudMesh Interconnect Service — Product Documentation

**Version 2.4** | Last updated: 2025-11-03

## Service Overview

CloudMesh Interconnect is a fully managed network fabric that provides low-latency, high-throughput connectivity between your cloud workloads, on-premises data centers, and edge locations. Interconnect supports both Layer 3 (routed) and Layer 2 (bridged) topologies with automatic failover and built-in encryption.

Interconnect integrates natively with CloudMesh VPC, CloudMesh Kubernetes Engine (CKE), and CloudMesh Bare Metal Services. Cross-cloud peering with AWS, Azure, and GCP is available through our Gateway Bridge feature (currently in **Public Preview**).

## Pricing

Interconnect pricing is based on three components:

| Component            | Rate                           |
| -------------------- | ------------------------------ |
| Attachment (per hub) | $0.05/hr per attachment        |
| Data processed       | $0.02/GB for first 10 TB/month |
| Data processed       | $0.01/GB for next 40 TB/month  |
| Data processed       | $0.005/GB above 50 TB/month    |

Prices above reflect intra-region traffic only. Cross-region data transfer incurs an additional surcharge depending on region pair (see Data Transfer section below).

> **Note:** Interconnect hubs deployed in premium-tier regions (ap-northeast-1, eu-west-3, me-south-1) carry a 1.35x multiplier on all attachment and data processing fees. This multiplier is applied after volume discounts.

Committed-use discounts of 20% are available on 1-year terms and 35% on 3-year terms. Committed-use applies to attachment fees only; data processing charges are not eligible.

## Quotas and Limits

| Resource                    | Default Limit | Maximum (with support request) |
| --------------------------- | ------------- | ------------------------------ |
| Hubs per account            | 5             | 25                             |
| Attachments per hub         | 20            | 50                             |
| Routes per hub route table  | 200           | 1,000                          |
| Bandwidth per attachment    | 10 Gbps       | 100 Gbps                       |
| Total bandwidth per hub     | 50 Gbps       | 200 Gbps                       |
| BGP sessions per attachment | 2             | 4                              |

Quota increases require 5 business days to process. Requests above the documented maximum limits require architecture review approval and may take up to 30 business days.^1

^1 During Q4 (October through December), quota increase requests may experience extended processing times of up to 45 business days due to freeze windows. Emergency requests are evaluated on a case-by-case basis and require VP-level approval from the customer organization.

## Regional Availability

Interconnect is generally available in the following regions:

- **North America:** us-east-1, us-west-2, ca-central-1
- **Europe:** eu-west-1, eu-central-1
- **Asia Pacific:** ap-southeast-1, ap-northeast-1

The following regions are in **Limited Preview** and require enrollment:

- us-west-1, eu-west-3, ap-south-1, me-south-1

There is no published timeline for GA in preview regions. Workloads in preview regions are not covered by the standard SLA (see SLA section).

## Gateway Bridge (Cross-Cloud Peering)

Gateway Bridge enables direct peering with AWS, Azure, and GCP through managed interconnect tunnels. This feature is in **Public Preview** and is subject to the following limitations:

- Maximum of 5 Gateway Bridge connections per account
- Throughput capped at 5 Gbps per connection
- Only available in us-east-1 and eu-west-1
- No SLA during preview
- Preview-to-GA migration path is not guaranteed; configuration changes may be required

## SLA

CloudMesh Interconnect carries a **99.95% monthly availability SLA** for hubs deployed in GA regions with redundant attachments (minimum two attachments in separate availability zones).

**SLA Exclusions:**

- Single-attachment hubs are not covered
- Hubs in preview regions are not covered
- Performance (latency/throughput) is not guaranteed under the SLA; only reachability is measured
- Planned maintenance windows (up to 8 hours/month, announced 48 hours in advance) are excluded from availability calculations
- Gateway Bridge connections are excluded from SLA coverage entirely
- Failures caused by exceeding documented quotas are excluded

Service credits are capped at 30% of the monthly Interconnect charges for the affected hub.

## Data Transfer

Intra-region data transfer between attachments on the same hub is billed at the standard data processing rate above.

**Cross-region data transfer** incurs additional charges:

| Route                                        | Surcharge (per GB) |
| -------------------------------------------- | ------------------ |
| Within same continent                        | $0.02              |
| Intercontinental (e.g., North America to EU) | $0.05              |
| To/from premium-tier regions                 | $0.08              |
| To/from preview regions                      | $0.12              |

Cross-region surcharges are **in addition to** the standard data processing rate. For example, sending 1 GB from us-east-1 to ap-northeast-1 (premium-tier, intercontinental) is billed at $0.02 (base) + $0.08 (premium surcharge) = $0.10/GB.

> **Important:** Data transfer through Gateway Bridge connections is billed at the cross-cloud rate of $0.15/GB, which applies regardless of region. This rate is additive with any applicable cross-region surcharges on the CloudMesh side of the connection. Both ingress and egress are metered for Gateway Bridge traffic, unlike standard Interconnect where only egress is charged.

## Encryption

All Interconnect traffic is encrypted in transit using AES-256-GCM. Customer-managed encryption keys (CMEK) are supported for hubs in GA regions only. Key rotation is automatic every 90 days; customer-initiated rotation is available via API.

## Support

Interconnect is covered under CloudMesh Enterprise Support plans. Critical issues (P1) have a 15-minute response target. Standard issues carry a 4-hour response target during business hours (Mon-Fri, 09:00-18:00 local time). Weekend support for non-critical issues is available only on the Premium support tier.
