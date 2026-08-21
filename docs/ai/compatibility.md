# Client Compatibility

The workflow content is provider-neutral Markdown. The skill entries follow the
Agent Skills open standard: a folder containing `SKILL.md` with YAML frontmatter.

| Client | Persistent project instructions | Skills | Agent definitions |
| --- | --- | --- | --- |
| Codex | `AGENTS.md` | Reads `.agents/skills/` when routed by `AGENTS.md` | Use the role files as delegation prompts |
| ChatGPT/GPT | Attach or connect the repository, then provide `AGENTS.md` as project context | Attach or provide the matching `SKILL.md` when a reusable procedure is needed | Provide the matching role file as the task instruction |
| Claude Code | `CLAUDE.md` imports `AGENTS.md` | `.claude/skills/` wrappers | `.claude/agents/` |
| Gemini CLI | `GEMINI.md` imports `AGENTS.md` | `.agents/skills/` is auto-discovered | `.gemini/agents/` |
| Antigravity | `.agents/rules/project-workflow.md` imports `AGENTS.md` | `.agents/skills/` | `.agents/agents/` |

## One-Time Checks

- **Claude Code:** start a new session and run `/skills`; the two project skills
  and two project agents should be listed.
- **Gemini CLI:** trust the workspace if prompted, then run `/skills list`; the
  skills should be listed. Use `@implementation-agent` or `@review-agent` to
  select a project subagent.
- **Antigravity:** in Customizations > Rules, set
  `.agents/rules/project-workflow.md` to **Always On** once. The Agent Manager
  should list the workspace agents; the Skills panel should list the skills.
- **Codex/GPT:** local files cannot force a remote or generic chat session to
  load repository context. Start in this repository (Codex) or attach/connect
  the repository (GPT) and explicitly reference `AGENTS.md` when the client
  does not expose project-context discovery.

No repository file can bypass a client's trust, workspace, or upload boundary.
These checks make the workflow explicit instead of relying on undocumented
auto-discovery.
