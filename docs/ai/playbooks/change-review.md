# Change Review Playbook

Use for pull-request review, pre-merge review, or changes touching SQL execution,
authentication, permissions, database connections, audit logging, masking, or
trace propagation.

1. Apply the `AGENTS.md` open-question session gate.
2. Read the applicable spec, ADR, and changed tests. Compare the diff against
   the stated acceptance criteria.
3. Check correctness, input validation, authorization, error translation,
   sensitive-data exposure, concurrency/connection lifecycle, and regressions.
4. Run or inspect the reported validation. Do not claim a command passed unless
   its actual result is available.
5. Report findings by severity with file path, concrete impact, and a proposed
   remedy. If no findings exist, state residual risk and unverified areas.
6. Do not edit production code as the reviewer unless the user asks for a fix.
