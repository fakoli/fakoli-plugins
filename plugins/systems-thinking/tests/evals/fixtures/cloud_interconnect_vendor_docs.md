# Multi-Cloud Interconnect Options — AWS-to-GCP Reference Guide

**Version 3.1** | Last updated: 2025-12-15

This document describes six interconnect options for establishing network connectivity between Amazon Web Services (AWS) and Google Cloud Platform (GCP). Each option is evaluated across pricing, quotas, SLA, regional availability, and operational considerations.

---

## Option 1: AWS Site-to-Site VPN with GCP HA VPN

### Overview

Establishes encrypted IPsec tunnels between AWS VPN Gateway and GCP HA VPN Gateway. Uses the public internet as transport with no dedicated bandwidth guarantees. Suitable for development/staging workloads or as a backup path for dedicated interconnects.

### Pricing

| Component | AWS Rate | GCP Rate |
|---|---|---|
| VPN tunnel (per tunnel, per hour) | $0.05/hr | $0.05/hr |
| Data transfer out (first 10 TB/month) | $0.09/GB | $0.12/GB |
| Data transfer out (next 40 TB/month) | $0.085/GB | $0.11/GB |
| Data transfer out (over 50 TB/month) | $0.07/GB | $0.08/GB |

> **Note:** Each HA VPN gateway requires a minimum of two tunnels for redundancy. A single HA VPN gateway pair therefore costs at minimum $0.20/hr ($0.05 × 2 tunnels × 2 sides). Data transfer is charged on both sides (dual-metered).

### Quotas and Limits

| Resource | AWS Limit | GCP Limit |
|---|---|---|
| VPN connections per VGW | 10 | N/A |
| Tunnels per VPN connection | 2 | N/A |
| HA VPN tunnels per gateway | N/A | 8 |
| Maximum throughput per tunnel | 1.25 Gbps | 3 Gbps |
| Aggregate throughput per VGW | 1.25 Gbps | N/A |
| BGP routes advertised (per session) | 100 (soft limit) | 5,000 (hard limit) |
| BGP routes learned (per session) | 100 (soft limit) | N/A |

> **Warning:** AWS VPN Gateway aggregate throughput is capped at 1.25 Gbps regardless of the number of tunnels. This is a hard architectural limit of the VGW and cannot be increased via support request. For higher throughput requirements, use AWS Transit Gateway or Direct Connect.

### SLA

| Component | SLA |
|---|---|
| AWS Site-to-Site VPN | 99.95% (with redundant tunnels across AZs) |
| GCP HA VPN | 99.99% (with proper HA configuration) |
| Combined end-to-end | No composite SLA published — lowest component applies |

**SLA Exclusions:**
- Single-tunnel configurations are not covered
- Internet path quality (latency, jitter, packet loss) is not guaranteed
- BGP convergence time after failover is not bounded by SLA
- Throughput is not guaranteed; SLA covers reachability only

### Regional Availability

Available in all standard AWS and GCP regions. HA VPN is not available in the following GCP regions (Legacy VPN only):

- asia-east2 (Hong Kong)
- australia-southeast2 (Melbourne)

### Operational Considerations

- VPN tunnel establishment takes 1-3 minutes on initial setup
- BGP session keepalive timers must match on both sides (AWS default: 30s, GCP default: 20s — mismatch will cause session flapping)
- MTU must be set to 1,400 bytes on the VPN tunnel interfaces to account for IPsec overhead; failure to set this causes silent packet drops on large frames
- AWS VPN metrics are only available in CloudWatch with a 5-minute delay; GCP VPN metrics are near-real-time in Cloud Monitoring

> **Caveat:** When using HA VPN with AWS, the "HA" designation applies only to the GCP side. The AWS VGW does not provide the same level of redundancy guarantees. For true HA across both clouds, deploy redundant VPN connections from two separate AWS regions.

---

## Option 2: AWS Direct Connect with GCP Partner Interconnect

### Overview

Uses AWS Direct Connect to reach a colocation facility, then a GCP Partner Interconnect from the same facility to GCP. Requires presence at a shared colocation point (e.g., Equinix, Megaport). Provides dedicated bandwidth with lower latency than VPN.

### Pricing

| Component | Rate |
|---|---|
| AWS Direct Connect port (1 Gbps) | $0.30/hr |
| AWS Direct Connect port (10 Gbps) | $2.25/hr |
| AWS Direct Connect data transfer out (DTO) | $0.02/GB (all tiers) |
| GCP Partner Interconnect (50 Mbps - 500 Mbps) | $0.03/hr per 50 Mbps increment |
| GCP Partner Interconnect (1 Gbps - 10 Gbps) | Partner-dependent pricing |
| GCP Partner Interconnect data egress | $0.05/GB (first 1 TB), $0.04/GB (next 9 TB) |
| Colocation cross-connect fee | $200-500/month per cross-connect (facility-dependent) |

> **Important:** AWS Direct Connect DTO pricing of $0.02/GB applies only to private virtual interfaces (VIFs). Public VIF traffic is charged at standard EC2 data transfer rates ($0.09/GB), which is 4.5x higher. Ensure all cross-cloud traffic routes through private VIFs.

### Quotas and Limits

| Resource | AWS Limit | GCP Limit |
|---|---|---|
| Direct Connect connections per region | 10 | N/A |
| Private VIFs per connection | 50 | N/A |
| BGP prefixes per private VIF | 100 (hard limit) | N/A |
| Partner Interconnect attachments per region | N/A | 16 (per project) |
| Maximum bandwidth per attachment | N/A | 50 Gbps |
| BGP prefixes advertised to GCP | N/A | 5,000 |
| Total BGP routes across all VIFs | 200 (per gateway) | N/A |

> **Critical:** The AWS BGP prefix limit of 100 per private VIF is a hard limit that cannot be increased. If your GCP environment advertises more than 100 routes, you must implement route summarization or use multiple VIFs. Exceeding this limit causes BGP session teardown with no warning — the session is simply dropped.

### SLA

| Component | SLA |
|---|---|
| AWS Direct Connect (resilient connections) | 99.99% |
| AWS Direct Connect (single connection) | 99.9% |
| GCP Partner Interconnect | 99.9% (single), 99.99% (redundant across metros) |

**SLA Exclusions:**
- Partner network segment is not covered by either AWS or GCP SLA
- Colocation facility power/cooling failures are excluded
- Cross-connect installation and repair times are facility-dependent and not covered
- Latency targets are not part of the SLA

### Regional Availability

**Shared colocation facilities** (Direct Connect + Partner Interconnect available):

| Metro | Facility | AWS DX Location | GCP Partner Location |
|---|---|---|---|
| Ashburn, VA | Equinix DC1-DC15 | Yes | Yes |
| Chicago, IL | Equinix CH1 | Yes | Yes |
| Dallas, TX | Equinix DA1 | Yes | Yes |
| Los Angeles, CA | Equinix LA1 | Yes | Yes |
| London, UK | Equinix LD5 | Yes | Yes |
| Frankfurt, DE | Equinix FR5 | Yes | Yes |
| Tokyo, JP | Equinix TY1 | Yes | Yes |
| Singapore | Equinix SG1 | Yes | Yes |

### Operational Considerations

- Direct Connect provisioning takes 2-4 weeks for new ports; GCP Partner Interconnect provisioning takes 1-2 weeks
- LOA-CFA (Letter of Authorization) from AWS expires after 90 days; if cross-connect is not installed by then, a new LOA must be requested
- Both sides require manual BGP configuration; there is no automated peering setup
- Monitoring requires correlating CloudWatch (AWS) and Cloud Monitoring (GCP) separately — no unified dashboard
- Failover from Direct Connect to VPN backup is not automatic unless you configure BGP MED/Local-Preference correctly

> **Caveat:** Partner Interconnect partners may impose their own bandwidth limits, SLA terms, and pricing that override or supplement the rates listed here. Always obtain a quote from the specific partner before sizing.

> **Caveat:** The colocation cross-connect lead time at some facilities (particularly in Tokyo and Singapore) can exceed 8 weeks during high-demand periods. Budget for this in your project timeline.

---

## Option 3: GCP Cross-Cloud Interconnect (Dedicated)

### Overview

Google's managed offering that provides a direct physical connection from GCP to AWS (or Azure). GCP provisions and manages both ends of the connection through partner facilities. This is the simplest option for customers who want a single-provider managed experience. **Launched GA in October 2024.**

### Pricing

| Component | Rate |
|---|---|
| Cross-Cloud Interconnect (10 Gbps) | $1,700/month |
| Cross-Cloud Interconnect (100 Gbps) | $17,000/month |
| Data transfer (GCP egress via CCI) | $0.05/GB (first 1 TB), $0.04/GB (1-10 TB) |
| Data transfer (AWS side) | Standard AWS data transfer rates apply |

> **Note:** The $1,700/month for 10G Cross-Cloud Interconnect includes the physical port on both sides and the cross-connect fees. However, AWS data transfer charges are separate and billed by AWS directly. The total cost is therefore $1,700/month (GCP) + AWS DTO ($0.02/GB for private VIF) + AWS hourly charges for the connected gateway.

### Quotas and Limits

| Resource | Limit |
|---|---|
| Cross-Cloud Interconnect connections per project | 8 |
| Maximum bandwidth per connection | 100 Gbps |
| VLAN attachments per connection | 16 |
| BGP prefixes (GCP to AWS) | 5,000 |
| BGP prefixes (AWS to GCP) | 100 (AWS-side limit applies) |
| Minimum connection size | 10 Gbps |
| Supported remote clouds | AWS, Azure, Oracle Cloud |

> **Important:** The minimum connection size is 10 Gbps. There is no option for smaller increments. Organizations needing less than 10 Gbps of cross-cloud bandwidth should consider Partner Interconnect or VPN instead.

### SLA

| Configuration | SLA |
|---|---|
| Redundant connections (2+ in different edge availability domains) | 99.99% |
| Single connection | 99.9% |

**SLA Exclusions:**
- AWS-side connectivity issues are not covered by the GCP SLA
- Maintenance windows (up to 4 hours/month) excluded from availability calculations
- Performance (throughput, latency) not guaranteed — only reachability
- Connections in preview regions excluded

### Regional Availability

Cross-Cloud Interconnect to AWS is available in the following GCP regions:

| GCP Region | Connected AWS Region | Edge Availability Domain |
|---|---|---|
| us-east4 (Ashburn) | us-east-1 (N. Virginia) | zone1, zone2 |
| us-central1 (Iowa) | us-east-2 (Ohio) | zone1, zone2 |
| us-west1 (Oregon) | us-west-2 (Oregon) | zone1, zone2 |
| europe-west2 (London) | eu-west-2 (London) | zone1, zone2 |
| asia-northeast1 (Tokyo) | ap-northeast-1 (Tokyo) | zone1 only |

> **Warning:** The Tokyo location currently has only one edge availability domain (zone1). This means you cannot achieve the 99.99% SLA in Tokyo — only the single-connection 99.9% SLA applies. A second edge availability domain is planned for **Q3 2026** but this timeline is not guaranteed.

### Operational Considerations

- Provisioning takes 5-10 business days for standard connections
- Connection bandwidth cannot be changed after provisioning; you must order a new connection at the desired speed and migrate traffic
- GCP manages the physical layer but does not manage BGP policy — you are responsible for route filtering and traffic engineering
- No built-in failover to VPN; this must be configured separately using Cloud Router
- Cross-Cloud Interconnect connections appear as standard Dedicated Interconnect attachments in the GCP console; there is no separate console view

> **Caveat:** Cross-Cloud Interconnect GA status does not extend to all listed regions. The asia-northeast1 (Tokyo) and europe-west2 (London) locations are in **Extended Preview** and subject to different terms. Preview location pricing may change at GA.

---

## Option 4: AWS Transit Gateway with GCP Network Connectivity Center

### Overview

Uses AWS Transit Gateway as the central routing hub on the AWS side and GCP Network Connectivity Center (NCC) on the GCP side, with VPN tunnels or interconnects connecting them. Suitable for hub-and-spoke topologies with multiple VPCs on both sides.

### Pricing

| Component | Rate |
|---|---|
| AWS Transit Gateway attachment (per VPC) | $0.05/hr |
| AWS Transit Gateway data processing | $0.02/GB |
| GCP NCC hub (per hub) | $0.05/hr |
| GCP NCC spoke attachment | No additional charge (included in hub) |
| VPN tunnels (if used for cross-cloud link) | $0.05/hr per tunnel (each side) |
| Data transfer | Standard rates per transport option chosen |

> **Note:** Transit Gateway data processing charges apply to ALL traffic traversing the TGW, including intra-region VPC-to-VPC traffic that merely passes through on its way to the cross-cloud link. This can significantly increase costs in hub-and-spoke deployments with high east-west traffic volumes.

### Quotas and Limits

| Resource | AWS Limit | GCP Limit |
|---|---|---|
| VPC attachments per TGW | 5,000 | N/A |
| Routes per TGW route table | 10,000 | N/A |
| TGW peering attachments | 50 | N/A |
| NCC hubs per project | N/A | 10 |
| NCC spokes per hub | N/A | 1,000 |
| Maximum TGW bandwidth per VPC attachment | 50 Gbps | N/A |
| Maximum TGW bandwidth per VPN attachment | 1.25 Gbps (ECMP: up to 50 Gbps) | N/A |

### SLA

| Component | SLA |
|---|---|
| AWS Transit Gateway | 99.99% |
| GCP Network Connectivity Center | 99.99% (GA regions) |

### Regional Availability

Transit Gateway is available in all AWS regions. NCC is available in all GCP GA regions. Cross-region NCC peering is available between all GA region pairs.

> **Note:** NCC is in **Preview** in the following GCP regions: africa-south1, me-central1, us-south1. Preview regions carry no SLA and pricing may change at GA.

### Operational Considerations

- Transit Gateway route tables require careful design to avoid routing loops when connected to NCC
- NCC spoke types (VPN, Interconnect, Router Appliance) have different failover characteristics
- TGW inter-region peering adds latency and an additional $0.02/GB data processing charge
- NCC does not support transitive routing between spokes by default; you must enable it explicitly
- Monitoring requires separate dashboards: CloudWatch for TGW, Cloud Monitoring for NCC

> **Caveat:** The combination of TGW and NCC creates a dual-control-plane topology. Route propagation changes on one side can take up to 60 seconds to converge on the other side. During convergence, traffic black-holing is possible. There is no single pane of glass for monitoring the combined topology.

---

## Option 5: SD-WAN Overlay (Third-Party)

### Overview

Deploy a third-party SD-WAN solution (e.g., Cisco Viptela, VMware SD-WAN, Palo Alto Prisma SD-WAN) that creates overlay tunnels between AWS and GCP. The SD-WAN controller manages routing, failover, and traffic engineering. Can use internet, VPN, or dedicated interconnects as underlay.

### Pricing

| Component | Rate |
|---|---|
| SD-WAN virtual appliance license | $500-3,000/month per appliance (vendor-dependent) |
| Cloud marketplace deployment fee | Varies by vendor |
| Underlay transport | Per transport option chosen (VPN, DX, Interconnect) |
| Controller/orchestrator | $1,000-10,000/month (cloud-hosted, vendor-dependent) |
| AWS compute for SD-WAN appliance | c5n.xlarge or similar: ~$250/month |
| GCP compute for SD-WAN appliance | n2-standard-4 or similar: ~$200/month |

> **Important:** SD-WAN pricing is highly variable and vendor-specific. The ranges above are indicative only. Most vendors require annual commitments with minimum seat counts. POC/trial periods are typically 30-90 days.

### Quotas and Limits

| Resource | Typical Limit |
|---|---|
| Maximum overlay tunnels per appliance | 32-64 (vendor-dependent) |
| Maximum throughput per appliance | 2-10 Gbps (depends on instance size and encryption) |
| Route table size | 10,000-50,000 routes (vendor-dependent) |
| Maximum sites per controller | 500-5,000 (licensing tier) |

### SLA

SD-WAN SLA is governed entirely by the vendor agreement. Cloud provider SLAs apply only to the underlying compute and network resources (VM uptime, VPC networking), not to the SD-WAN overlay performance.

> **Warning:** Many SD-WAN vendors advertise "99.999%" availability but this refers to the control plane (orchestrator), not the data plane. Data plane availability depends on underlay path diversity and is typically 99.9%-99.99%.

### Regional Availability

Available wherever you can deploy virtual appliances — effectively all AWS and GCP regions. Controller/orchestrator must be reachable from all sites.

### Operational Considerations

- Adds a third vendor to the support matrix (cloud provider + cloud provider + SD-WAN vendor)
- Firmware/software updates on SD-WAN appliances require coordination with both cloud providers
- SD-WAN appliances consume cloud compute resources; right-sizing is critical to avoid throughput bottlenecks
- Troubleshooting requires access to SD-WAN controller, AWS console, and GCP console simultaneously
- Some SD-WAN vendors do not support GCP natively and require manual deployment via marketplace images

> **Caveat:** SD-WAN appliances deployed in cloud lose many of the advantages of hardware-based SD-WAN (dedicated ASICs, hardware crypto acceleration). Cloud-deployed SD-WAN typically delivers 40-60% of the throughput advertised for hardware equivalents.

> **Caveat:** Lock-in risk is high. Migrating from one SD-WAN vendor to another requires re-architecting the entire overlay network. Budget 3-6 months for vendor migration projects.

---

## Option 6: Megaport Virtual Edge (MVE) with Megaport Cloud Router (MCR)

### Overview

Uses Megaport's software-defined network fabric to connect AWS and GCP without requiring physical colocation presence. MVE provides a virtual routing function in Megaport's network, and MCR enables Layer 3 routing between cloud on-ramps. This is a "NaaS" (Network as a Service) approach.

### Pricing

| Component | Rate |
|---|---|
| MCR (1 Gbps) | $500/month |
| MCR (5 Gbps) | $1,500/month |
| MCR (10 Gbps) | $2,500/month |
| Virtual Cross Connect to AWS (VXC, 1 Gbps) | $500/month |
| Virtual Cross Connect to GCP (VXC, 1 Gbps) | $500/month |
| MVE (if needed for SD-WAN/firewall overlay) | $650-2,800/month |
| Data transfer | Included in VXC pricing (no per-GB charges from Megaport) |

> **Note:** While Megaport does not charge per-GB data transfer fees, both AWS and GCP still charge their standard egress rates. The Megaport pricing covers the network fabric transit only.

> **Important:** MCR pricing is based on port speed, not utilization. A 10 Gbps MCR at 10% utilization costs the same as one at 90% utilization. Right-size the MCR to avoid overpaying.

### Quotas and Limits

| Resource | Limit |
|---|---|
| VXCs per MCR | 24 |
| Maximum MCR bandwidth | 10 Gbps |
| BGP sessions per VXC | 1 |
| BGP prefixes per session | 1,000 (Megaport limit) |
| MVE regions | 23 (as of December 2025) |
| MCR regions | 27 (as of December 2025) |
| Minimum VXC speed | 50 Mbps |
| Maximum VXC speed | 10 Gbps |

### SLA

| Component | SLA |
|---|---|
| MCR availability | 99.9% |
| VXC availability | 99.9% |
| MVE availability | 99.9% |
| End-to-end (Megaport fabric) | 99.9% (composite) |

> **Note:** The 99.9% SLA applies to the Megaport fabric only. Combined with cloud provider SLAs, the effective end-to-end SLA is lower. Megaport does not offer a 99.99% tier for MCR.

### Regional Availability

MCR is available in the following shared metro locations:

| Metro | AWS Direct Connect | GCP Partner Interconnect |
|---|---|---|
| Ashburn | Yes | Yes |
| Chicago | Yes | Yes |
| Dallas | Yes | Yes |
| Silicon Valley | Yes | Yes |
| London | Yes | Yes |
| Frankfurt | Yes | Yes |
| Sydney | Yes | Yes |
| Tokyo | Yes | Yes |
| Singapore | Yes | Yes |
| São Paulo | Yes | No — **GCP Partner Interconnect not available** |
| Mumbai | Yes | Yes (Preview) |

> **Warning:** São Paulo MCR can connect to AWS but not to GCP. Mumbai GCP connectivity is in **Preview** status with no SLA. Verify current availability with Megaport before designing for these locations.

### Operational Considerations

- MCR provisioning is near-instant (minutes); VXC provisioning takes 1-5 business days depending on cloud provider
- Megaport provides a single portal for managing both AWS and GCP connections
- No physical infrastructure to manage; all components are virtual
- Megaport looking glass available for BGP troubleshooting
- MCR does not support route filtering by community — only prefix-based filtering
- VXC redundancy requires ordering two VXCs to different cloud on-ramp locations

> **Caveat:** Megaport's MCR does not support IPv6 BGP peering. If your cross-cloud traffic includes IPv6, you must deploy MVE with a virtual router that supports IPv6 or use a different interconnect option entirely.

> **Caveat:** Megaport's portal API rate limits are 100 requests/minute. Infrastructure-as-code deployments (Terraform, Pulumi) that manage many VXCs may hit this limit during plan/apply cycles. Implement retry logic with exponential backoff.

---

## Cross-Cutting Concerns

### Encryption

| Option | Encryption in Transit | Encryption at Rest | FIPS 140-2 |
|---|---|---|---|
| VPN (Option 1) | AES-256 (IPsec) | N/A | Yes (AWS), Yes (GCP) |
| Direct Connect + Partner (Option 2) | Optional (MACsec on DX, none on Partner) | N/A | MACsec only |
| Cross-Cloud Interconnect (Option 3) | MACsec (optional, 100G only) | N/A | MACsec only |
| TGW + NCC (Option 4) | Per transport option | N/A | Per transport |
| SD-WAN (Option 5) | AES-256 (vendor overlay) | N/A | Vendor-dependent |
| Megaport MCR (Option 6) | None by default — unencrypted Layer 3 | N/A | No |

> **Critical:** Megaport MCR traffic traverses the Megaport fabric **unencrypted**. If regulatory or compliance requirements mandate encryption in transit, you must add your own encryption layer (IPsec tunnels, application-level TLS, etc.) on top of the MCR connection. This adds latency and reduces effective throughput.

### Compliance and Data Residency

- All options except VPN (Option 1) involve data traversing third-party physical infrastructure (colocation facilities, partner networks, Megaport fabric)
- Data residency requirements may restrict which interconnect options are available in specific jurisdictions
- HIPAA BAAs are available from AWS and GCP but must be separately obtained from any third-party interconnect providers
- PCI DSS scope may extend to the interconnect layer depending on what data traverses the connection

### Disaster Recovery Considerations

For cross-cloud DR, the interconnect must support:
1. Sufficient bandwidth for replication traffic (typically 10-30% of production traffic)
2. Failover time within RTO requirements
3. Monitoring that detects failures faster than the RPO window

| Option | Typical Failover Time | Bandwidth Scalability | Cost at 10 TB/month Transfer |
|---|---|---|---|
| VPN (Option 1) | 30-90 seconds (BGP convergence) | Limited (1.25 Gbps max on AWS) | ~$2,100/month |
| Direct Connect + Partner (Option 2) | 1-5 minutes (manual) or 30s (with BGP) | High (up to 100 Gbps) | ~$3,300/month |
| Cross-Cloud Interconnect (Option 3) | 30-60 seconds (BGP) | High (10-100 Gbps per connection) | ~$2,500/month |
| TGW + NCC (Option 4) | 30-60 seconds (BGP) | Medium-High | ~$2,800/month |
| SD-WAN (Option 5) | 5-15 seconds (overlay path switching) | Medium (2-10 Gbps per appliance) | ~$4,000-7,000/month |
| Megaport MCR (Option 6) | 30-60 seconds (BGP) | Medium (up to 10 Gbps) | ~$2,000/month |

> **Note:** Cost estimates for 10 TB/month assume us-east region pair and include both cloud provider egress charges and interconnect fees. Actual costs will vary based on traffic patterns, commitment terms, and negotiated rates.

### Monitoring and Observability

No single monitoring solution covers all six options end-to-end. Each option requires:

- Cloud-provider-native monitoring (CloudWatch, Cloud Monitoring)
- Interconnect-specific monitoring (Megaport portal, SD-WAN controller, partner portals)
- BGP session monitoring (custom or via cloud provider route table APIs)
- Latency and packet loss probes (synthetic monitoring recommended)

> **Recommendation:** Deploy synthetic monitoring probes (e.g., AWS Network Monitor, GCP Connectivity Tests) on both sides of every interconnect to establish baseline latency and detect degradation before it impacts applications.

---

## Summary Comparison

| Criterion | VPN | DX + Partner | Cross-Cloud IC | TGW + NCC | SD-WAN | Megaport |
|---|---|---|---|---|---|---|
| Setup Time | Hours | 4-8 weeks | 1-2 weeks | Hours + transport | 1-2 weeks | Days |
| Max Bandwidth | 1.25 Gbps (AWS) | 100 Gbps | 100 Gbps | Per transport | 2-10 Gbps | 10 Gbps |
| HA SLA | 99.99% (GCP only) | 99.99% (each side) | 99.99% | 99.99% | Vendor | 99.9% |
| Encryption | Built-in | Optional | Optional | Per transport | Built-in | None |
| Vendors Involved | 2 | 3+ | 2 | 2 | 3+ | 3 |
| Operational Complexity | Low | High | Medium | Medium-High | High | Medium |
| Best For | Dev/staging, backup | High-bandwidth production | Simplicity, managed | Multi-VPC hub-spoke | Policy-based routing | Fast deployment, NaaS |

---

## Appendix A: BGP Configuration Reference

### AWS BGP Defaults

- ASN: 64512 (default, configurable)
- Hold time: 90 seconds
- Keepalive: 30 seconds
- Graceful restart: Supported but not enabled by default
- BFD: Supported on Direct Connect VIFs (not on VPN)
- Maximum prefix limit per VIF: 100 (hard limit, session dropped on exceed)

### GCP BGP Defaults

- ASN: 16550 (default for Cloud Router, configurable)
- Hold time: 60 seconds
- Keepalive: 20 seconds
- Graceful restart: Enabled by default
- BFD: Supported on Cloud Router (Preview status)
- Maximum prefix limit per session: 5,000 (configurable, up to 10,000 with support)

> **Warning:** The mismatch between AWS (100 prefix limit) and GCP (5,000 prefix limit) is the most common cause of connectivity issues in AWS-to-GCP interconnects. Design route summarization on the GCP side to stay well below the AWS 100-prefix limit.

## Appendix B: Compliance Certification Matrix

| Certification | AWS (native) | GCP (native) | Megaport | Equinix |
|---|---|---|---|---|
| SOC 2 Type II | Yes | Yes | Yes | Yes |
| ISO 27001 | Yes | Yes | Yes | Yes |
| PCI DSS | Yes | Yes | No | Yes (facility) |
| HIPAA | Yes (BAA) | Yes (BAA) | No BAA available | N/A |
| FedRAMP | Yes (High) | Yes (Moderate) | No | N/A |

> **Critical:** Megaport does not offer HIPAA BAAs or PCI DSS certification. If regulated data (PHI, cardholder data) traverses the Megaport fabric, additional compensating controls or a different interconnect option may be required.

## Appendix C: Version History

| Version | Date | Changes |
|---|---|---|
| 3.1 | 2025-12-15 | Added Megaport MCR option, updated Cross-Cloud Interconnect GA status |
| 3.0 | 2025-09-01 | Added SD-WAN option, expanded DR comparison table |
| 2.0 | 2025-03-15 | Added Cross-Cloud Interconnect (Preview), TGW+NCC option |
| 1.0 | 2024-11-01 | Initial release with VPN, DX+Partner options |
