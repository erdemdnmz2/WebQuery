# Documentation

Start with the [project README](../README.md), then read only what your task needs.

| Document | Purpose |
| --- | --- |
| [Architecture](architecture.md) | Runtime boundaries and retained technical decisions |
| [Implemented features](features.md) | Behavior, source and test mapping; limitations |
| [Configuration](configuration.md) | Complete environment reference and safe setup |
| [Development](development.md) | Bootstrap, local execution and validation |
| [Migration analysis](migration-analysis.md) | What was kept, consolidated or left behind, and why |
| [Implementation plan](implementation-plan.md) | Ordered remaining work, not delivered functionality |
| [Open questions](open-questions.md) | Decision queue; currently no active open items |
| [Frontend design](../frontend/DESIGN.md) | Tokens, components and accessibility rules |

Historical spec/ADR IDs are mapped in the migration analysis. Their absence as
individual files does not authorize changing accepted behavior. New behavior
uses the [spec template](specs/SPEC-TEMPLATE.md); durable decisions use the
[ADR template](adr/ADR-TEMPLATE.md). Record reviewed work with the
[handoff template](handoffs/HANDOFF-TEMPLATE.yaml).

Workflow procedures remain under `ai/playbooks/`; provider-specific adapters,
old handoffs and duplicate implementation roadmaps are deliberately not imported.
