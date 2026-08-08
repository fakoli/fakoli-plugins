# Archived Plugins

This directory contains plugins that were moved out of the active marketplace because they are too project-specific to be useful to the general community.

## Archived Entries

### k8s-sidecar-testing
A plugin built for a specific Kubernetes sidecar testing workflow. Archived because it tightly couples to a single internal project's container topology and has no meaningful reuse outside that context.

### rust-network-module
A plugin built around a specific Rust networking module. Archived because it targets one internal codebase's module structure and is not applicable to general Rust networking development.

## Policy

Plugins land here when they meet one or more of the following criteria:

- They encode assumptions specific to a single internal project or repo.
- They have no documented reuse path for outside users.
- They were superseded by a more general plugin in `plugins/`.

These criteria are about **reuse value**, not about how often any one operator
happens to invoke a plugin. A plugin that goes unused on one machine already
costs that machine nothing once it is disabled locally, while archiving it here
removes it for every consumer of the marketplace. Local context cost is a
configuration decision (`enabledPlugins`), not an archive decision — see
[docs/ROSTER-PRUNE.md](../docs/ROSTER-PRUNE.md).

Archived plugins are kept for historical reference and are not published to the marketplace registry.
