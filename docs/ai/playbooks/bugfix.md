# Bug Fix Playbook

Use when restoring intended behavior without intentionally changing the public
contract.

1. Apply the `AGENTS.md` open-question session gate.
2. State the observed behavior, expected behavior, and a reliable reproduction.
3. Add a failing regression test first when practical. If the expected behavior
   is unclear, create a mini-spec instead of guessing.
4. Fix the smallest root cause; do not mix unrelated refactoring into the fix.
5. Run the regression test and relevant nearby suite. Use a YAML handoff if the
   result moves to another session or reviewer.

Create an ADR only when the fix deliberately introduces a durable architecture
or security decision.
