---
inclusion: manual
---
# /sync-docs: on-demand documentation sync

(Kiro IDE 1.x recommends manual steering files instead of manual hooks for on-demand workflows.)

1. Read `git diff --stat HEAD~10` and the current `.kiro/specs/*/design.md`.
2. Update `README.md` (setup, run, demo mode), `docs/architecture.md` (Mermaid diagram of frontend → API → Strands agent → tools → Chroma/SQLite/Bedrock) and the API section (list every route with request and response schema).
3. If the stack or structure changed, update `.kiro/steering/tech.md` or `structure.md` with minimal edits.
4. Don't touch application code.
