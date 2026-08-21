---
name: spec-and-adr
description: Creates or updates a WebQuery feature specification and, when a durable trade-off exists, its ADR. Use for new or changed API behavior, business rules, security behavior, or architecture decisions.
---

# WebQuery Spec and ADR

Apply the open-question gate in `AGENTS.md` first. Do not choose answers for
open questions.

Read `docs/ai/playbooks/feature-delivery.md` for behavior changes and
`docs/ai/playbooks/architecture-decision.md` for durable technical choices.

Use `docs/specs/SPEC-TEMPLATE.md` for the spec. Use
`docs/adr/ADR-TEMPLATE.md` only when a durable architecture, security, data,
dependency, or operational trade-off exists. Do not create a `.feature` file
unless its scenarios will be executable.
