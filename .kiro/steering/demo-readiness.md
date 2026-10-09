---
inclusion: manual
---
# /demo-readiness: pre-pitch verification checklist

The 90-minute cut line is the deterministic seeded/cached path: fixed proposal → review → one OVERLAPPING and one COMPLEMENTARY verdict → memo → approver action → gap redirect/map state. Run blocking checks first and report `check | pass/fail | fix applied`.

## Blocking demo checks
1. Check ports before starting services; never start a second instance.
2. Run `python scripts/demo_smoke.py` in `DEMO_MODE=cached`; it must reproduce the canonical scenario, including both labels, memo, approval/rejection state, and redirect map state without Bedrock.
3. Confirm every scripted response is locally available under the canonical cache key and that the minimal pipeline/API/frontend shared-ID schema smoke test passes.
4. Confirm seeded badges and an actual snapshot date are visible; use `TBD: needs source` when the date is unavailable.

## Secondary evidence checks
Bedrock reachability, full indexing, full golden evaluation, complete pytest/Vitest runs, 1366×768 screenshots, and pitch-evidence collection are secondary if the blocking path works. Run them only when time permits. Do not require clean git status or a `demo-ready` tag before demonstration.

Don't change product behaviour in this pass. Fix only what blocks the demo.
