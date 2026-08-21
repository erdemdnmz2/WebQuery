# AI Development Workflow

This directory contains provider-neutral playbooks. `AGENTS.md` selects them;
the native files for Claude Code, Gemini CLI, and Antigravity only make them
discoverable in each client.

## Normal Change Flow

1. Apply the open-question gate in `AGENTS.md`.
2. Select a playbook.
3. Create the smallest required artifact: spec, ADR, executable feature, or
   regression test.
4. Implement and validate.
5. Write a YAML handoff when the work is handed to another person/agent,
   reviewed asynchronously, or paused.

## Compatibility

See `docs/ai/compatibility.md` for the exact repository paths used by each
client and the one-time activation checks.
