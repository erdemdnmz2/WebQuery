# Contributing

Use a short-lived branch and a pull request. Keep changes focused and preserve
unrelated work. The main branch should not be edited directly.

Before changing behavior, read [current contracts](docs/features.md) and
[architecture](docs/architecture.md), resolve active
[open questions](docs/open-questions.md), and write a spec using
[the template](docs/specs/SPEC-TEMPLATE.md). Use an ADR for a durable design or
security boundary, not every routine edit. Plans are not implemented features.

For UI work read [DESIGN.md](frontend/DESIGN.md) first. For SQL, authorization,
credentials, logging, masking or cancellation use the
[change-review playbook](docs/ai/playbooks/change-review.md).

Run the applicable commands in [development](docs/development.md): backend
pytest/correctness lint, frontend typecheck/build and API/contrast/export checks,
plus root repository checks. Add regression tests for fixes. State skipped
live-service tests and environment differences honestly in the PR; no frontend
test runner currently exists. Never run destructive CI database tests on real data.

Keep documentation current with its code and test references. Do not add a
second roadmap or copy old session reports into feature specs. Use the handoff
template for long-running/review work.

Never commit `.env`, database backups, tokens, real customer examples or resolved
Compose secret output. Use synthetic data. If a secret leaked, rotate it;
adding a Git ignore rule does not remove history or revoke access.

Contributions are made under the repository license. Preserve existing notices
and the licenses/attributions of any imported third-party material.
