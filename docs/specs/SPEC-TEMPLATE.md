# Mini-Spec: `<Feature name>`

## 1. Spec card

- Feature: `<Short name>`
- Status: Draft | Ready for implementation | Implemented | Superseded
- Version: `<semver or date>`
- Date: `<YYYY-MM-DD>`
- Owner: `<person or team>`

## 2. Purpose and success signal

### Purpose

`<User or business problem.>`

### Success signal

- `<Observable and testable result>`

## 3. Scope / exclusions

### Scope

- `<Included behavior>`

### Exclusions

- `<Behavior explicitly excluded from this change>`

## 4. Contract

`<Describe the endpoint, UI flow, event or data contract. Add request/response examples when needed.>`

## 5. Business rules

### BR-01: `<Rule name>`

`<A clear, unambiguous rule.>`

## 6. Acceptance criteria

- AC-01: Given `<starting state>`, when `<action>`, then `<verifiable result>`.
- AC-02: `<Error, authorization or boundary case>`.

## 7. Technical and security constraints

- `<Performance, compatibility, data, authentication, audit or masking constraint>`

## 8. Open questions

- `<OQ-YYYY-NNN>`: `<Question>`

If a question is open, also add it to `docs/open-questions.md`. Status can be
`Ready for implementation` only after open questions are resolved or explicitly
deferred by the user.

## 9. Done check

- [ ] Tests were added or updated for the acceptance criteria
- [ ] Relevant security and error behavior was verified
- [ ] An ADR was created or updated when required
- [ ] Validation commands were run and results were written to the handoff
