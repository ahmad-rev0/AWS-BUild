# agent/ — local rules (always loaded by Kiro for this folder)

- This folder is the Strands agent service. Read `.kiro/steering/agent-guardrails.md` rules as binding.
- Never put prompt text in Python; load from `agent/prompts/*.md`.
- Deterministic facts (geo/time/sector overlap, need score) come from tools in `agent/tools/`, never from the model.
- Every new tool needs: docstring written for the model, Pydantic input/output, one unit test, and (if deterministic) a Hypothesis property test.
- Run tests with: `.venv/bin/pytest agent/tests -q -k <name>` (narrowest first).
