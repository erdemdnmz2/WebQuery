# Mini-Spec: English language baseline

## 1. Spec card

- Feature: English product language for the main application
- Status: Implemented
- Version: 2026-10-08
- Date: 2026-10-08
- Owner: WebQuery maintainer

## 2. Purpose and success signal

### Purpose

Make the main WebQuery application consistently usable in English. The
translation covers the frontend UI, accessibility labels, API diagnostics,
Slack approval messages, operational logs, source comments and maintained
project documentation that currently contain Turkish text.

### Success signal

- The tracked main application contains no Turkish runtime text or Turkish
  technical prose outside historical migration context and repository
  governance templates that are intentionally preserved as working agreements.
- The main frontend presents the same English copy already validated in the
  local demo build.
- Existing API shapes, identifiers, role values, SQL behavior, security
  controls and data values are unchanged.

## 3. Scope / exclusions

### Scope

- Translate tracked frontend presentation literals, HTML metadata, locale
  formatting and accessibility text into English.
- Translate backend API error/detail messages, domain messages, CLI prompts,
  Slack messages, operational logs and comments/docstrings.
- Translate maintained product and development documentation where Turkish
  prose remains, while preserving code, identifiers, historical migration
  semantics and security rules.
- Update automated assertions and documentation references that intentionally
  assert the old Turkish wording.

### Exclusions

- No runtime i18n framework, language selector or new dependency.
- No renaming of existing English methods, routes, payload fields, database
  columns, role enums, SQL identifiers or migration identifiers.
- No changes to authorization, audit logging, masking, tracing, query analysis,
  connection handling or stored data.

## 4. Contract

The presentation language of the main application is English. Response shapes,
status codes, route paths, request and response field names, role values and
canonical data normalization remain unchanged. API messages and Slack
notifications use English text.

## 5. Business rules

### BR-01: Preserve machine-facing values

Translation edits may change human-language literals only. Values used for
matching, normalization, authorization, masking, SQL, routing or persistence
must remain byte-for-byte compatible unless a test assertion itself only
references translated human text.

### BR-02: Keep security behavior intact

The translation must not alter query risk analysis, authorization decisions,
masking behavior, audit events, trace propagation, rate limits or secret
handling.

### BR-03: Keep historical migrations stable

Already committed migration identifiers and schema operations remain unchanged.
Only comments or diagnostic text may be translated when doing so does not
change migration behavior.

## 6. Acceptance criteria

- AC-01: Login, registration, workspaces, SQL Studio, administration, owner
  flows, command palette, dialogs, empty/loading/error states and accessibility
  labels render in English.
- AC-02: Backend API diagnostics, CLI prompts, Slack approval messages and
  operational logs use English where the application controls the text.
- AC-03: No Turkish identifiers are introduced or left in executable source;
  existing machine-facing identifiers and canonical `tr` normalization remain
  unchanged.
- AC-04: Frontend typecheck, build, API contract audit, contrast audit and
  export/source-map checks pass.
- AC-05: Backend tests pass with updated assertions for translated messages;
  security-sensitive behavior remains covered.
- AC-06: Repository hygiene passes and the final worktree contains only the
  intended tracked changes.

## 7. Technical and security constraints

- Use the existing local English frontend as the source for exact UI wording
  where it matches the current tracked frontend.
- Do not print or copy credentials, tokens, environment values or database
  contents.
- Do not translate arbitrary user-provided SQL, usernames, database names,
  query text or server-provided data at runtime.
- Keep the existing design tokens, accessibility contract and security audit
  coverage intact.

## 8. Open questions

None. The user explicitly requested an English main application.

## 9. Done check

- [x] Acceptance criteria have corresponding validation
- [x] Security and error behavior have been checked
- [x] Frontend and backend validation commands have passed
- [x] Relevant documentation and assertions have been updated
