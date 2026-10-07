# Open Questions

No active project questions have status `Open`.

### OQ-2026-023: Clean public repository scope

- Status: Answered
- Raised: 2026-10-06
- Scope: Repository migration and documentation selection
- Question: Which source files and documents belong in the new repository?
- Answer: The user's cleanup request authorizes selecting working source, tests,
  migrations and build configuration, consolidating documentation against the
  implementation, and maintaining a complete environment example and README.
  Historical handoffs, duplicate plans and local-only material are not copied.
- Recorded in: [Baseline spec](specs/SPEC-0033-public-repository-baseline.md),
  [migration analysis](migration-analysis.md)

## Entry format

Use `Open`, `Answered`, `Deferred` or `Superseded`. Ask every `Open` item at the
start of a session before task work. Do not silently assume an answer.

```md
### OQ-YYYY-NNN: Short question

- Status: Open
- Raised: YYYY-MM-DD
- Scope: Affected feature or decision
- Question: Exact decision to resolve
- Why it matters: Consequences of the alternatives
- Answer:
- Recorded in:
```
