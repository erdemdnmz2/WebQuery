# Feature Delivery Playbook

Use for a new or changed API contract, UI behavior, business rule, or security
behavior.

1. Apply the `AGENTS.md` open-question session gate. Stop after asking all
   active questions until the user answers or defers them.
2. Create or update the feature spec from `docs/specs/SPEC-TEMPLATE.md`. Give
   business rules and acceptance criteria stable IDs.
3. If the task changes a durable architecture, data/security boundary, external
   dependency, or contains a material trade-off, write a proposed ADR from
   `docs/adr/ADR-TEMPLATE.md` before implementation.
4. Add a `.feature` file only if the Gherkin scenarios will be executed by a BDD
   runner. Otherwise retain the acceptance criteria in the spec and write normal
   pytest or frontend tests.
5. Implement the smallest change that meets the acceptance criteria. Update
   tests with the behavior.
6. Run the relevant validation. Record actual commands and results in a handoff
   when the work will be reviewed, paused, or delegated.
