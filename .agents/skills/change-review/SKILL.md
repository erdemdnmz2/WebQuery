---
name: change-review
description: Reviews WebQuery changes for correctness, contract adherence, and security-sensitive regressions. Use for code review or changes to SQL execution, auth, permissions, database connections, audit logs, masking, or tracing.
---

# WebQuery Change Review

Apply the open-question gate in `AGENTS.md` first. Then read and follow
`docs/ai/playbooks/change-review.md`.

Do not edit production code unless the user asks for a fix. Report only findings
supported by the diff, repository evidence, or actual validation output.
