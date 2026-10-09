# Implementation Plan: Atlas11 Clash Review Agent

## Overview

Implement the clash review agent in dependency order: shared contracts and durable store first; deterministic facts and validator next; constrained Strands orchestration and cached mode after that; then FastAPI/SSE, approvals/audit, evaluation, and the cached integration gate. Every Hypothesis property task is required. The fixed cached demo is the blocking end-to-end validation; live Bedrock reachability is secondary.

## Tasks

- [x] 1. Establish shared clash-review contracts and storage
  - [x] 1.1 Extend `agent/schemas.py` with typed Pydantic contracts for proposal intake/persistence, statuses, role, review creation, all four verdict labels, memo recommendations, `ClashReport`, approvals, SSE events, overlap facts, and audit events.
  - [x] 1.2 Add model validators for ordered proposal dates, finite confidence in `[0,1]`, non-empty rejection reasons, redirect-only memo district, and stable canonical IDs/source labels.
  - [x] 1.3 Implement `agent/store.py` SQLite schema and typed repository operations for proposals, reviews, approvals, and append-only audit events, including transactional completion/approval writes.
  - [x] 1.4 Add focused contract/store tests for validation, proposal insertion, atomic review completion, approval persistence, and sanitized audit rows.

- [ ] 2. Implement deterministic review tools and taxonomy validator
  - [x] 2.1 Add `agent/tools/search_similar_projects.py` with a model-facing docstring, Pydantic input/output, `k <= 8` enforcement, and shared retrieval delegation returning IDs/scores only.
  - [x] 2.2 Add `agent/tools/get_project.py` with a model-facing docstring, Pydantic input/output, canonical lookup, provenance preservation, and typed not-found failure.
  - [x] 2.3 Add `agent/tools/check_overlap.py` with a model-facing docstring and deterministic canonical city/district, sector/beneficiary, concrete-output, and inclusive 12-month date-slack facts.
  - [x] 2.4 Add `agent/tools/district_need.py` and `agent/tools/draft_memo.py`, each with a model-facing docstring and Pydantic contracts; keep redirects explicitly non-financial.
  - [~] 2.5 Implement post-processing validator logic that enforces geographic/time/district severity constraints, conservative missing-date behavior, evidence consolidation, bounded confidence, and the duplicate-to-overlapping downgrade plus audit event.
  - [~] 2.6 Add unit tests for each tool and every taxonomy rule, including city mismatch, known/unknown districts, missing/boundary dates, shared beneficiaries, concrete outputs, and duplicate evidence downgrade.
  - [~] 2.7 Add required Hypothesis properties for overlap symmetry, cross-city final-label exclusion, duplicate evidence minimum, and verdict label/confidence closure.

- [ ] 3. Implement constrained Strands/Nova review orchestration
  - [~] 3.1 Create `agent/prompts/clash_system.md` containing the concise taxonomy, structured-output contract, and model-role constraints; do not place prompt content in Python.
  - [~] 3.2 Create `agent/clash_agent.py` with exactly one Strands `Agent`, loading the prompt file and Nova Pro model configuration from refreshed environment values.
  - [~] 3.3 Implement live candidate selection: filter on city, optional district, sector, and implementation window; retrieve at most eight and send at most five deterministic candidate packages to Nova Pro.
  - [~] 3.4 Implement 20-second Bedrock timeout, `ClashReport` parse attempt, exactly one validation-feedback retry, readable second-failure error, and only post-validation taxonomy enforcement.
  - [~] 3.5 Reuse credential mapping and refresh dotenv/boto3 session per live request or credential failure; map expired tokens to the exact HTTP-503-ready `CredentialsExpired` message without logging secrets.
  - [~] 3.6 Add mocked orchestration tests for success, candidate cap, valid report, retry-success, retry-failure, tool failure, timeout, and credentials expiry.

- [ ] 4. Implement FastAPI review API, SSE, and lifecycle rules
  - [~] 4.1 Create `agent/app.py` with `POST /proposals`, `POST /proposals/{id}/review`, `GET /reviews/{id}/events`, `GET /reviews/{id}`, `POST /approvals`, and `GET /audit`, using only shared Pydantic response payloads.
  - [~] 4.2 Implement review lifecycle guards: only `SUBMITTED` proposals create reviews; valid completed reports move `SUBMITTED -> REVIEWED` atomically; failures retain `SUBMITTED`; report retrieval exposes only validated completed reports.
  - [~] 4.3 Implement SSE serialization and event choreography: `status -> tool_call(s) -> verdict(s) -> done`, or `error` instead of `done`; include tool name/duration and final review reference.
  - [~] 4.4 Implement API exception mapping for not-found, conflict, validation, denied role, agent schema failure, cache unavailability, tool errors, and exact expired-credential 503 JSON body.
  - [~] 4.5 Add FastAPI/SSE tests for all endpoint responses, lifecycle failures, payload shapes, success/error ordering, validated report retrieval, and credential-expiry output.
  - [~] 4.6 Add required Hypothesis properties for approval state-machine reachability and SSE ordering/terminal-event exclusivity.

- [ ] 5. Add approval authority and complete audit coverage
  - [~] 5.1 Implement approval transitions permitting only `role=approver` to move `REVIEWED -> APPROVED | REJECTED`, requiring a reason for rejection and preventing repeat/skip transitions.
  - [~] 5.2 Ensure every proposal, review, tool call, verdict, downgrade, completion/failure, approval/rejection attempt, and successful decision appends the required ID/actor/role/timestamp/summary audit data.
  - [~] 5.3 Add tests that denied transitions leave status unchanged, approval never triggers financial behavior, and `GET /audit` filters and redacts secrets correctly.

- [ ] 6. Implement deterministic cached-demo path
  - [~] 6.1 Add the canonical seeded cache payload under `data/demo_cache/` for `scenario_key=demo-city-transit-01` and `proposal_id=demo-proposal-01`, with source label, valid report, one `OVERLAPPING`, one `COMPLEMENTARY`, `CO_FINANCE`, and redirect district ID.
  - [~] 6.2 Route `DEMO_MODE=cached` at the API layer to parse and serve the local cache without constructing/invoking Bedrock or live retrieval; return an actionable error if cache data is missing or invalid.
  - [~] 6.3 Provide deterministic/local approval and redirect/gap response state for the canonical scenario, retaining the rule that redirect changes coordination focus only.
  - [~] 6.4 Add cached-mode tests with AWS/retrieval mocks that fail if called, then assert deterministic report, valid SSE order, seeded source, approval/rejection behavior, redirect state, and cache-error preservation.

- [ ] 7. Implement and exercise golden-pair evaluation
  - [~] 7.1 Create `agent/eval.py` to load labelled `data/eval/golden_pairs.jsonl`, run deterministic/agent classification evaluation, and append timestamped summaries to `.kiro/evidence/eval-history.csv`.
  - [~] 7.2 Implement `--quick` to evaluate only the first six valid pairs and full mode to evaluate all valid pairs, with useful label-level results and readable malformed-pair reporting.
  - [~] 7.3 Add/obtain at least 12 human-labelled pairs spanning every verdict, city/date boundaries, missing dates, district mismatch, and the canonical demo; preserve seeded/fetched provenance.
  - [~] 7.4 Add evaluation tests and run the narrow quick evaluation. Confirm prompt-file changes use the existing regression hook and do not reduce golden-pair accuracy without review.

- [ ] 8. Run the integration gate and focused quality checks
  - [~] 8.1 Add `scripts/demo_smoke.py` that runs the canonical submit → cached review → SSE → report → approver action → redirect/gap flow without AWS or Chroma.
  - [~] 8.2 Add the minimal shared-schema smoke test covering pipeline project IDs, API Pydantic payloads, and frontend-facing serialized review IDs; use it as the end-to-end integration gate.
  - [~] 8.3 Run the changed `pytest` unit/property/API suites and cached demo smoke test inside the activated venv; run Ruff format/lint for changed Python files.
  - [~] 8.4 Record only factual results and blockers in evidence; do not claim that seeded records, redirect state, or approval created funding or impact.

## Task Dependency Graph

```json
{
  "waves": [
    {"id": 0, "tasks": ["1.1", "1.2", "1.3"]},
    {"id": 1, "tasks": ["1.4", "2.1", "2.2", "2.3", "2.4"]},
    {"id": 2, "tasks": ["2.5", "2.6", "3.1"]},
    {"id": 3, "tasks": ["2.7", "3.2", "3.3", "3.4", "3.5"]},
    {"id": 4, "tasks": ["3.6", "4.1", "4.2"]},
    {"id": 5, "tasks": ["4.3", "4.4", "5.1", "5.2"]},
    {"id": 6, "tasks": ["4.5", "4.6", "5.3", "6.1", "6.2", "6.3"]},
    {"id": 7, "tasks": ["6.4", "7.1", "7.2", "7.3"]},
    {"id": 8, "tasks": ["7.4", "8.1", "8.2", "8.3", "8.4"]}
  ]
}
```

## Notes

- Execute tasks one at a time. Begin supervised for the contract, tool, and orchestration tasks; proceed only after their focused tests pass.
- The property-based tasks in 2.7 and 4.6 are required. Preserve a failing Hypothesis counterexample if one occurs; it is evidence for a later bugfix workflow rather than a reason to weaken the property.
- The cached canonical flow is the first and blocking demo test. Live Bedrock, full index availability, and full evaluation are secondary once it passes.
