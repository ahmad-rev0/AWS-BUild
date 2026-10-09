---
inclusion: manual
---
# /pitch-evidence: compile "How we used Kiro" for the Technical Implementation criterion

Judges ask: *"Does the team clearly explain **why and how** they used specific Kiro functionalities?"* Produce `docs/kiro-usage.md` with one row per feature:

| Kiro feature | Where it is in the repo | What we used it for | Why this feature (not another) | Evidence (file, screenshot, metric) |

Cover all of these: steering (always / fileMatch / auto / manual modes), feature specs (Requirements-First and Design-First), Quick Spec, Bugfix spec, EARS requirements, property-based tests (Correctness), task execution, agent hooks (each one), MCP servers, Powers, Agent Skills, custom agents and subagents, context providers (#spec #steering #codebase #terminal #problems #git diff #url), checkpoints, Autopilot vs Supervised mode, and model selection per phase.

Sources to read: `.kiro/**`, `.kiro/evidence/prompt-log.md`, `git log --oneline`, the eval results in `.kiro/evidence/eval-history.csv`.

Then write a **45-second spoken script** (≈110 words) at the end of the file. It covers the three most impressive uses:
1. EARS requirements → property-based tests that caught a real bug
2. The hook that regression-tests the agent's prompt on every save (show the accuracy history)
3. Steering that encodes our SDG-11 taxonomy and human-approval guardrail

Use real numbers from the evidence files only (see data-honesty).
