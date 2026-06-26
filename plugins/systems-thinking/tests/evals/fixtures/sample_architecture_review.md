# Multi-Region Connectivity Architecture — Design Review

**Author:** Platform Engineering Team
**Date:** 2025-10-15
**Status:** Draft — Pending Approval

## Overview

This document describes the proposed network architecture for connecting our primary (us-east-1) and disaster-recovery (eu-west-1) regions through CloudMesh Interconnect. The design supports active-passive failover for our customer-facing API tier and active-active replication for the data layer.

The target state is full production traffic capability in both regions with an RPO of 15 minutes and RTO of 30 minutes.

## Components

### Network Fabric

- **Primary hub:** CloudMesh Interconnect hub in us-east-1 with 4 attachments (2 per AZ)
- **DR hub:** CloudMesh Interconnect hub in eu-west-1 with 2 attachments (1 per AZ)
- **Cross-region peering:** Hub-to-hub peering via CloudMesh backbone
- **DNS failover:** CloudMesh Global DNS with health checks at 30-second intervals

### Compute

- CKE clusters in both regions running the API service
- Auto-scaling groups configured with min=2, max=20 in primary; min=1, max=10 in DR

### Data Layer

- CloudMesh Distributed SQL (primary in us-east-1, read replica in eu-west-1)
- Asynchronous replication with configurable lag alert threshold (default: 5 minutes)
- Object storage with cross-region replication enabled

### Observability

- Metrics pipeline: CloudMesh Monitoring with cross-region dashboard
- Centralized logging in us-east-1 (logs ship from eu-west-1 via Interconnect)

## Traffic Flow

1. Client DNS resolves to primary region via Global DNS
2. Traffic enters through CloudMesh Load Balancer to CKE ingress
3. API pods query Distributed SQL and object storage
4. Cross-region replication runs continuously on the data layer
5. On failover, DNS health check triggers cutover to eu-west-1

## Dependencies

- CloudMesh Global DNS for failover routing
- CloudMesh Distributed SQL cross-region replication feature (GA)
- CloudMesh Interconnect hub-to-hub peering
- Gateway Bridge for connectivity to on-premises monitoring (via AWS Direct Connect in us-east-1)
- CloudMesh Service Mesh v2 for mTLS between regions (**Public Preview**, expected GA Q2 2026)

## Security

- All cross-region traffic encrypted via Interconnect (AES-256-GCM)
- mTLS between services using Service Mesh v2 certificate authority
- Network policies restrict cross-namespace traffic in CKE
- IAM roles scoped per service with region-specific permissions

## Capacity Planning

- Expected steady-state cross-region data transfer: ~500 GB/day
- Peak replication burst during batch processing: up to 2 TB/hour
- DR region sized at 50% of primary capacity

## Rollout Plan

1. Phase 1: Deploy Interconnect hubs and verify peering (Week 1-2)
2. Phase 2: Deploy CKE clusters and service mesh in DR (Week 3-4)
3. Phase 3: Enable data replication and validate RPO (Week 5-6)
4. Phase 4: Configure DNS failover and run failover drill (Week 7-8)

## Open Questions

- What is the fallback if Service Mesh v2 GA is delayed past Q2 2026?
- Do we need dedicated Interconnect bandwidth reservations for replication bursts?
- Who owns the failover runbook — Platform Engineering or SRE?
