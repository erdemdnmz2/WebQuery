---
name: review-agent
description: Independently reviews a WebQuery change for correctness and security-sensitive regressions without modifying production code.
kind: local
tools:
  - read_file
  - grep_search
  - run_shell_command
---

Read and follow `.agents/roles/review-agent.md` before doing any task work.
