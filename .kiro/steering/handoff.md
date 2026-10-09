---
inclusion: manual
---
# /handoff: write a session handoff before switching Kiro accounts

The team uses several Kiro accounts **one after another**. Chat history does not carry over between accounts, but the repository does. When this file is invoked:

1. Read every `.kiro/specs/*/tasks.md` and list each task's status: done, in progress or not started.
2. Run `git status --short` and `git log --oneline -10`.
3. Overwrite `.kiro/evidence/HANDOFF.md` with:
   - **Current spec and task** (exact task number and title)
   - **What was just completed** (3 bullets max)
   - **What is half-done** and the exact next step
   - **Known issues or failing tests** (with the command to reproduce)
   - **Hook states** (which hooks are enabled or disabled, and why)
   - **Environment notes** (servers running, ports, whether `.env` credentials were refreshed and when)
4. Commit with the message `chore: handoff <timestamp>`.
5. Reply with a 3-line summary only.

When a new account starts, its first prompt is:
`#steering handoff is done. Read .kiro/evidence/HANDOFF.md and #spec <current-spec>, then continue from the next step.`
