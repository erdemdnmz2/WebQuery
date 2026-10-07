# Mini-Spec: Clean public repository baseline

## 1. Spec card

- Feature: Public repository packaging and documentation cleanup
- Status: Implemented
- Version: 2026-10-07
- Date: 2026-10-07
- Owner: WebQuery maintainer

## 2. Purpose and success signal

Provide a readable, reproducible public baseline without importing legacy
repository clutter or making undocumented application behavior changes.
Documentation must distinguish implemented behavior, known limitations and
future work; an implementation plan is not evidence of delivery.

## 3. Scope / exclusions

Include runtime source, tests, the complete Alembic revision chain, lockfiles,
build/CI files, curated documentation and safe example configuration.

Exclude legacy Git history, secrets, backups, dependency installations, local
virtual environments, local-only documents and historical session handoffs.
Do not modify the source repository, merge branches or change GitHub settings.
The initial preparation excluded publication; the maintainer's subsequent
"transfer to the new repo" request authorizes committing and publishing this
baseline on its own branch/PR. It does not authorize merging into main.
Schema changes and new application features require separate specs.

## 4. Contract

Import from legacy `main` at `6cf0a73` rather than the security-hardening branch:
this baseline includes the MSSQL fixes and merged query cancellation.
Backend/frontend behavior and the existing test suite remain unchanged.
New ignore rules exclude local secrets from Git and Docker build contexts;
example files contain blank secret values, not usable production credentials.

## 5. Business rules

- BR-01: Copy only selected tracked files from the named source commit.
- BR-02: Preserve migrations, authorization, audit, masking, trace propagation
  and cancellation behavior. Record gaps as future work, not silent fixes.
- BR-03: Keep the new Apache-2.0 license and preserve the original MIT notice
  for imported legacy code.
- BR-04: Keep one backend environment template at repository root; explain
  working-directory requirements and conditional settings explicitly.
- BR-05: No passing badge, production-readiness claim or test result without
  supporting evidence.

## 6. Acceptance criteria

- AC-01: Imported runtime/test/migration files match the selected commit except
  explicitly recorded packaging/documentation reference edits.
- AC-02: Git and each Docker build context ignore environment files, local
  dependencies, caches and backups, while example configuration remains tracked.
- AC-03: Every runtime environment setting is covered by the example and
  configuration reference; mandatory secrets are blank.
- AC-04: README setup matches the actual frontend port, owner bootstrap,
  metadata migration and Redis requirements.
- AC-05: Legacy document dispositions map implemented features to source and
  tests; pending behavior is retained in an ordered implementation plan.
- AC-06: Backend pytest and frontend build/checks are attempted and the actual
  results, including infrastructure-dependent omissions, are recorded.

## 7. Technical and security constraints

Never read, copy, print or commit real secret values. Ignore rules are preventive
controls, not a credential scanner or protection for already tracked files.
The default Docker topology is not a complete production deployment: HTTPS,
trusted-proxy scope, backups and restore validation still need operator setup.

## 8. Open questions

OQ-2026-023 is answered by the cleanup request. No active open questions.

## 9. Done check

- [x] AC-01 through AC-06 verified and handoff completed (live CI remains unrun)
- [x] Known risks and unapplied implementation steps documented
- [x] No unrelated source-repository changes or unapproved publication

AC-01 evidence: imported file/AST comparison, documentation-only Python deltas
and the isolated lockfile patch recorded in SPEC-0034. AC-02/03/05 use
`scripts/check_repository.py` and its seven regression tests. AC-04 is matched
against the runtime bootstrap/port configuration. AC-06 results and environment
differences are in `docs/handoffs/2026-10-07-clean-baseline.yaml`.
