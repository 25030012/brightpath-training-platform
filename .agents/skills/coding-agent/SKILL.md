---
name: coding-agent
description: >
  Issue-driven coding agent workflow combining Superpowers (brainstorming,
  planning, verification) and Ponytail (minimal, reuse-first implementation)
  with Chrome DevTools browser verification.
---

# Coding Agent Skill

When picking up an issue or request that asks for something to be built, follow this exact checklist in order:

1. **Brainstorm first (`brainstorming` skill)**
   - Read the domain data and existing codebase before asking a single question.
   - Ask clarifying questions one at a time (as comments on the issue or in chat) and wait for the user's reply.
   - Write **no code** until all questions have been answered.

2. **Write a plan and wait for approval (`writing-plans` skill)**
   - Write a clear implementation plan and post it on the issue (or in chat/docs).
   - Start building **only** after the user explicitly replies `approve` (or approves the plan).

3. **Build the Ponytail way (`ponytail` skill)**
   - Reuse what exists in the codebase, standard library, or platform before writing anything new.
   - Write only what the task needs—the smallest complete change that solves the problem without bloat or unrequested features.
   - Maintain validation at trust boundaries, error handling, and security.

4. **Verify in the browser (`verification-before-completion` + Chrome DevTools MCP)**
   - Before declaring any module done, start the server and verify every "Done when" criterion in the browser using Chrome DevTools MCP / browser tools.

5. **Report**
   - Report on the issue (or to the user):
     - What was built
     - What was checked
     - What was skipped and any known risks
