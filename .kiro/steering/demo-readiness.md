---
inclusion: manual
---
# /demo-readiness: pre-pitch verification checklist

Run each check, then report a table: check | pass/fail | fix applied.

1. `python scripts/check_aws.py`: Bedrock reachable? If not, confirm `DEMO_MODE=cached` works.
2. Start the API and frontend if they aren't running. Check the ports first.
3. Run the scripted demo scenario end to end via `python scripts/demo_smoke.py`. It must reproduce: one OVERLAPPING (recommend co-finance), one COMPLEMENTARY, the memo, an approval and the gap redirect.
4. Run `python -m agent.eval` (full golden set). Report accuracy and per-label results.
5. Run `pytest -q` and `npm --prefix frontend run test -- --run`.
6. Verify `data/demo_cache/` has a cached response for every scripted step.
7. Check the UI at 1366×768 (use the Playwright MCP to take screenshots into `docs/screenshots/`).
8. Confirm the seeded-data badges and data snapshot date are visible.
9. `git status` is clean, and the last commit is tagged `demo-ready`.
Don't change product behaviour in this pass. Fix only what blocks the demo.
