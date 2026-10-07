# Architecture Decision Playbook

Use before choosing a long-lived technical design, infrastructure dependency,
data boundary, security boundary, or significant operational trade-off.

1. Apply the `AGENTS.md` open-question session gate.
2. Define the scenario and identify the most decisive criterion. Do not score
   alternatives before the criterion is clear.
3. Compare at least two credible alternatives using
   `docs/adr/ADR-TEMPLATE.md`. Include only criteria that influence this
   decision.
4. Write the decision, rejected alternatives, consequences, and accepted risks.
   Mark the ADR `Proposed` until the authorized decision-maker accepts it.
5. Link the related feature spec and update it when the decision changes the
   implementation contract.
