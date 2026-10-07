# Legacy-to-public baseline analysis

## Selected source and provenance

- Runtime source: legacy `main`, commit
  `6cf0a732f5388b01edeecb8528ff9f0fcb0bc91c`.
- Target branch: `chore/clean-baseline`. The new Apache-2.0 `LICENSE` is retained;
  original MIT notice is preserved in `licenses/WebQuery-legacy-MIT.txt` and NOTICE.
- The source worktree is not modified. Its uncommitted decisions are noted
  separately below; they are not treated as delivered runtime changes.
- No source Git history, `.env`, credentials, backups, node_modules or virtual
  environment is copied. Runtime/test/migration files come from tracked source.
- Keep all 11 Alembic revisions and existing tests. Do not flatten schema history
  just because the repository history starts fresh.

The selected source includes MSSQL boolean/result-set fixes and merged query
cancellation. The security-validation-hardening branch is not a safe substitute:
it lacks later fixes and contains different frontend-test history.

## Documentation disposition

Legacy `docs/` has **108 tracked files**: 28 specs (including template), 25 ADRs
(including template), 32 handoffs, 14 inbox notes, 6 AI docs, one question queue,
one cancellation plan and one staging runbook. The new structure consolidates
behavior and decisions, keeps only reusable templates/playbooks and adds one
baseline spec, one targeted dependency spec and one review handoff: **18 files**
under `docs/`. `frontend/DESIGN.md` remains the UI
contract; it is not discarded as redundant documentation.

| Legacy spec IDs | Legacy ADR IDs | Current home / code evidence |
| --- | --- | --- |
| 0001, 0002 | 0003, 0004, 0005 | Configuration/architecture; guard, provider, engine cache |
| 0003, 0004, 0006, 0020 | 0006, 0007, 0009 | Features/architecture; target error sanitation, timeout, audit/logging |
| 0005, 0015, 0016, 0017 | 0008, 0012, 0013, 0014 | Features/configuration; sessions, account activation, Redis login protection |
| 0010, 0011, 0012, 0014 | 0010 | Frontend design/features; UI/API alignment, UUID normalization, truthful masking indicators |
| 0013 | 0011, 0019 | Features/architecture; atomic approval service and Slack payload |
| 0018 | 0001, 0015 | Architecture/development; complete migration chain and schema guard |
| 0019, 0021, 0022 | 0016, 0017 | Features/architecture; analyzer boundaries, OWNER, hardening fixes |
| 0024, 0025 | 0018 | Features; table-aware masking and removed dead execution/blacklist code |
| 0026, 0027 | 0021 | Development/features; explicit dev override and target lifecycle |
| 0029 | 0024 | Features/CI; dependency remediation and maintained XLSX export |
| 0030 | 0002, 0025 | CI/development; real MSSQL migration/runtime job, not an outstanding absence |
| 0032 | 0027 (Proposed) | Features/architecture; existing cancellation implementation and its limits |
| 0031 (draft), PLAN-0031 | 0026 (Proposed) | Implementation plan P1; proposed header/state/PubSub design not imported as delivered |

IDs above are historical references, not newly accepted decisions. Consolidation
does not resolve the cancellation design/policy differences. Preserve those
distinctions in future specs and reviews rather than promoting Proposed to Accepted.

### Inbox notes

| Legacy filename / topic | Disposition |
| --- | --- |
| `DATABASE-REGISTRATION-LIFECYCLE`, `TARGET-TRANSACTION-COMMIT` | Closed behavior exists; consolidated in features with lifecycle/transaction tests |
| `DEPENDENCY-ADVISORY-UPGRADES` | Old backlog remediated in source; existing blocking audits retained; current advisories require a fresh run |
| `MSSQL-VERIFICATION-GAP`, `CI-SIGNAL-AND-VERIFICATION-GAPS` | Real MSSQL CI now exists; remaining staging/frontend/live-driver gaps retained in P0/P2/P6 |
| `LEGACY-CENTRAL-CREDENTIAL-FALLBACK` | P3, still implemented compatibility |
| `IS-ADMIN-MIRROR-COLUMN` | P5, still present in model/event/tests |
| `DATABASE-EXTERNAL-IDENTIFIER-UUID` | P5, admin integer IDs and name-pair saved-query references remain |
| `GCP-STAGING-DEPLOYMENT-READINESS`, `TRUSTED-PROXY-SUBNET-VERIFICATION` | P2, environment-specific evidence absent; no claim of an established GCP/VPN deployment |
| `MULTI-RESULT-SET-REPORTING` | Deferred product contract, not a completed runner feature |
| `OPTIONAL-DESTRUCTIVE-DML-CONFIRMATION`, `RUNNING-QUERIES-IN-NAVBAR` | User-deferred work preserved as deferred |
| `AUDIT-REMEDIATION-COMMIT-SERIES-BISECTABILITY` | Historical legacy commit-series issue; not copied into fresh history |

The staging runbook's meaningful requirements (sanitized restore, upgrade,
schema guard and critical smoke paths) become P2. No claimed production rehearsal
is carried forward without new evidence. Old handoffs and root audit reports
are historical snapshots, not current specs, and remain in the untouched legacy
repository rather than the public tree. Provider adapter duplicates are omitted;
AGENTS, shared skills/roles and four playbooks remain.

### Uncommitted source-worktree material

ADR-0022 accepts removing the role-derived admin mirror; ADR-0023 and SPEC-0028
set customer-isolated VPN deployment direction. They are not part of the named
main commit and their runtime/deployment changes are not implemented. Their
meaning is retained in architecture/plan, without overwriting source drafts or
claiming they were merged. Local readiness/review notes inform the gap analysis
but are not copied wholesale. Explicitly local-only planning material is excluded.

## Corrections and safe optimization in this pass

- Replace stale MIT-only README wording and static passing badge with accurate
  Apache/legacy notices and no unsupported status claim.
- Correct frontend dev port to 3000 and first-OWNER bootstrap order.
- Replace duplicate incomplete backend env templates with one complete root
  example, blank secrets, production cookie defaults and local profile guidance.
- Add a backend `.dockerignore`: root ignore rules do not govern `build: ./web_api`.
  Tighten frontend/root contexts and Git exclusions for local secrets/artifacts.
- Make Compose configuration shortcuts quiet so they do not print resolved secrets.
- Keep application behavior unchanged. Update obsolete documentation references
  in comments/docstrings and the schema-guard operator log pointer; no change to
  API status codes or schema checks. Record schema/performance changes in the plan.
- Fresh audit found GHSA-68fv-2mgg-jv7q. The sole dependency-resolution change is
  `source-map-js` 1.2.1 → 1.2.2, with a failing-then-passing regression check and
  blocking CI verification; see SPEC-0034. All unrelated resolutions are retained.
- Add repository hygiene validation so env coverage and documentation links do not
  drift again. This is not a full secret scanner or frontend behavioral suite.

## Remaining risk and verification

See [features](features.md) for behavior limits and [implementation plan](implementation-plan.md)
for prioritized work. The current review evidence is recorded in
[the handoff](handoffs/2026-10-07-clean-baseline.yaml). Initial preparation was
local-only. The maintainer then authorized transfer to the new public repository;
the prepared baseline is published on a separate branch/PR without merging main
or changing GitHub settings.
