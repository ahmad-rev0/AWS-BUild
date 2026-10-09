# Atlas11 MVP Completion — Requirements

## Summary

Complete the remaining Atlas11 MVP work across the existing data-pipeline, clash-agent, gap-finder, and planner-dashboard specifications. The delivered product must demonstrate one reliable, end-to-end, human-in-the-loop urban-project coordination scenario: seeded proposal intake, deterministic cached review, structured memo, approver decision, audit trail, and a non-financial gap-map redirect. The implementation must preserve source provenance and distinguish seeded or illustrative material from sourced data.

The primary release criterion is the offline-capable cached demo scenario, not live Bedrock or a fully rebuilt vector index. The canonical scenario is `scenario_key=demo-city-transit-01` and `proposal_id=demo-proposal-01`; it must return exactly one `OVERLAPPING` verdict, exactly one `COMPLEMENTARY` verdict, and a `CO_FINANCE` recommendation. No feature may make, imply, or simulate a payment, allocation, commitment increase, or actual funding redirect.

**Assumptions**

- Existing completed work and current public API/schema intent in the four specifications are authoritative unless validation exposes a defect.
- The externally managed API process already on port 8000 must be reused; the completion work must not start a competing API instance.
- The frontend may be created from scratch, but must consume the existing FastAPI contracts rather than introduce a parallel backend contract.
- Bedrock model availability may vary by workshop account. A configured/exposed compatible Nova Pro model ID is acceptable; cached mode must not depend on it.
- The existing local project, GeoJSON, need-score, demo-cache, and evaluation files are the available data boundary. Missing provenance or snapshot data must be exposed as `TBD: needs source`, not invented.

## Functional Requirements

### 1. Shared contracts, data integrity, and provenance

1.1 The system shall use shared stable canonical IDs for projects, proposals, reviews, districts, and the canonical demo across pipeline data, API payloads, cache data, SQLite records, and frontend contracts.

1.2 Every backend API payload and agent output shall be represented by a Pydantic model, and every frontend REST/SSE boundary shall reject malformed payloads and unknown enum values before application state is updated.

1.3 Project and proposal records shall preserve `source` and, where available, `source_url`; seeded records shall have `source=seeded` and be visibly labelled “Seeded for demo” in the frontend.

1.4 District need records shall preserve `indicator_quality` (`measured`, `estimated`, or `illustrative`), provenance, and an actual snapshot date or `TBD: needs source`. The gap map and its legend shall make illustrative/estimated indicators explicit.

1.5 The system shall not fabricate real-world project, funder, impact, snapshot, or funding claims. A redirect or approval shall be described and represented only as a coordination focus/sign-off.

### 2. Data pipeline, embeddings, and retrieval

2.1 The index builder shall validate `data/processed/projects.csv` and any separate optional seeded-project input against the shared project contract, report independently rejected rows and reasons, and reject conflicting duplicate IDs.

2.2 The builder shall canonicalize the searchable project content, calculate deterministic content hashes, create or reopen the persistent local Chroma `projects` collection in `data/index/`, and support incremental re-indexing that skips unchanged records, re-upserts changed records, removes stale IDs, and commits its manifest atomically.

2.3 `EMBEDDINGS_PROVIDER=local` shall use `sentence-transformers/all-MiniLM-L6-v2` without an implicit network download in offline mode. `EMBEDDINGS_PROVIDER=bedrock` shall use Bedrock Titan Text Embeddings V2 with a 20-second bound and refreshed environment credentials.

2.4 The retrieval service shall accept a query, `k` no greater than 8, and supported canonical city, district, sector, and inclusive implementation-date-window filters. It shall return no more than `k` unique candidates, with normalized scores in `[0,1]`, descending deterministic order, and only candidates satisfying requested filters.

2.5 AWS diagnostics shall independently check configured Nova Pro and Titan embedding availability without printing secrets. Expired workshop credentials shall surface the exact actionable message: `AWS credentials expired. Refresh agent/.env from Workshop Studio.`

### 3. Clash review, taxonomy, and live-provider resilience

3.1 The system shall expose deterministic model tools for similar-project search, project lookup, overlap facts, district need, and memo drafting. Each tool shall use Pydantic input/output models, preserve provenance, and reside in its own documented file under `agent/tools/`.

3.2 The review taxonomy shall classify each proposal/candidate pair as exactly one of `DUPLICATE`, `OVERLAPPING`, `COMPLEMENTARY`, or `UNRELATED`. Geography shall be evaluated by canonical IDs first; candidates in different cities shall never receive `DUPLICATE` or `OVERLAPPING`.

3.3 The taxonomy validator shall apply inclusive implementation dates with exactly 12 months of slack at both ends. If required dates are missing, it shall conservatively avoid using time evidence to establish `DUPLICATE` or `OVERLAPPING`.

3.4 A `DUPLICATE` verdict shall require at least two matching attributes and concrete-output evidence; insufficient duplicate evidence shall be downgraded to `OVERLAPPING` and recorded in the audit trail. When facts are incomplete, the final label shall be less severe with appropriately bounded confidence.

3.5 Live review shall filter candidates by city, optional district, sector, and implementation window; retrieve no more than eight candidates; and provide no more than five deterministic candidate packages to the Strands/Nova review agent. The system prompt shall be maintained in `agent/prompts/clash_system.md`, not in Python source.

3.6 Live Bedrock calls shall time out after 20 seconds. Invalid model output shall be parsed as a `ClashReport`, receive at most one validation-feedback retry, and then fail with a readable API error. Credential failures shall map to the required 503 response and never expose credentials or stack traces.

### 4. FastAPI review lifecycle, SSE, approvals, and audit

4.1 FastAPI shall provide typed JSON/SSE endpoints for proposal creation, review creation, review events, completed-report retrieval, approvals, audit retrieval, and gap retrieval. The API shall run on port 8000; no second instance may be started when that port is already occupied.

4.2 Only a `SUBMITTED` proposal may create a review. A successfully validated report shall atomically change the proposal to `REVIEWED`; failed reviews shall retain `SUBMITTED`; completed reports shall be retrievable only after successful validation.

4.3 A review event stream shall emit `status`, zero or more `tool_call` events with tool name and duration, zero or more `verdict` events, and exactly one terminal event: `done` on success or `error` on failure. Events after a terminal event shall not affect frontend state.

4.4 Only `role=approver` may transition a `REVIEWED` proposal to `APPROVED` or `REJECTED`; rejection shall require a non-whitespace reason. Invalid, repeated, skipped, or denied transitions shall leave the proposal status unchanged.

4.5 Proposal submission, review lifecycle events, tool calls, final verdicts, taxonomy downgrades, approval/rejection attempts, and successful decisions shall append redacted, timestamped, role/actor-attributed audit records. Audit output shall not disclose credentials or secrets.

4.6 An approval is a human coordination sign-off only. Neither approval nor rejection shall call payment, allocation, funding, commitment, or money-movement behavior.

### 5. Cached deterministic demo and gap service

5.1 With `DEMO_MODE=cached`, the canonical scenario shall load and Pydantic-validate a local cache response from `data/demo_cache/` by its scenario key/proposal ID, without constructing or invoking Bedrock, Chroma retrieval, or AWS services.

5.2 The canonical cached report shall be seeded, contain exactly two verdicts—one `OVERLAPPING` and one `COMPLEMENTARY`—and produce a `CO_FINANCE` memo/recommendation and valid `redirect_district_id`.

5.3 Cached mode shall support deterministic/local proposal state, review SSE ordering, report retrieval, approver approval/rejection, audit records, and redirect/gap response state. Missing or invalid cache data shall return a readable actionable error while preserving proposal-state safety.

5.4 The gap builder shall validate local district GeoJSON and indicators, require matching canonical district universes, compute deterministic need scores and visible funding-per-capita classifications locally, preserve existing output on invalid/staging failures, and atomically publish a complete `data/geo/need_scores.csv`.

5.5 `GET /gaps` shall return a deterministic sorted collection or one requested district. It shall return 404 for an unknown canonical district and 503 for missing, malformed, or unavailable complete gap data; it shall not recalculate scores or write files during reads.

5.6 A redirect shall focus the selected district in API/UI state without changing need scores, commitments, funding-per-capita data, or gap classifications.

### 6. Planner dashboard

6.1 A React 18 + Vite + strict TypeScript + Tailwind CSS single-page dashboard shall be created under `frontend/`. It shall use React Leaflet/Leaflet and OpenStreetMap tiles, with local district GeoJSON and need-score assets, and shall use exact pinned dependency versions.

6.2 The dashboard shall provide a typed proposal form, Planner/Approver role toggle, review workflow state, REST client, cancellable SSE client, runtime payload validation, readable API errors, and a persistent non-blocking credential-expiry banner when the specified 503 response occurs.

6.3 A planner shall be able to submit the seeded canonical proposal, observe non-blank streamed progress, see final verdicts and memo, and retain form data after a non-successful API response. The client shall fetch the persisted report after a successful `done` event.

6.4 The dashboard shall show verdict label text, confidence, matching attributes, reasoning, project identity where resolved, provenance, and a selected-candidate map action. It shall represent all four labels with text and the specified closed palette: `DUPLICATE #C0392B`, `OVERLAPPING #D68910`, `COMPLEMENTARY #138D75`, and `UNRELATED #7F8C8D`.

6.5 The map workspace shall render an accessible need-score choropleth, legend, project/proposal markers, selected-candidate highlighting, and proposal-to-candidate lines only when both coordinates exist. Missing map data or coordinates shall display a localized unavailable state and leave review/approval functions usable.

6.6 The right-side memo/trace/decision drawer shall be closed by default, keyboard accessible, and remain operable at 1366×768 without collapsing the left proposal panel. It shall show the recommendation, redirect wording, agent trace, and approval outcome.

6.7 Approve/Reject controls shall be available only to an Approver for a final `REVIEWED` report. Planner users shall be told why approver authority is required; failed/denied decisions shall preserve reviewed state. All decision/redirect language shall state coordination only and never claim funding.

6.8 The canonical frontend path shall visibly show the seeded badge, exactly one `OVERLAPPING` and one `COMPLEMENTARY` result, `CO_FINANCE`, approver action, and redirect-map focus. It shall work when AWS and Bedrock are unavailable in cached mode.

### 7. Evaluation, validation, and operational completion

7.1 A golden-pair evaluator shall load valid labelled pairs from `data/eval/golden_pairs.jsonl`, support a six-pair `--quick` execution and full execution, report malformed pairs readably, and append factual timestamped results to `.kiro/evidence/eval-history.csv`. The dataset shall contain at least twelve human-labelled pairs covering all labels, city/date boundaries, missing dates, district mismatch, and the canonical demo, with provenance retained.

7.2 Focused Python tests shall cover contracts, SQLite lifecycle/approval/audit behavior, deterministic tools and taxonomy, cache behavior, pipeline/retrieval rules, gaps, API/SSE error ordering, and required Hypothesis invariants. Focused frontend tests shall cover parsers/transport, workflow behavior, provenance visibility, decision availability, UI components, and map/redirect invariants.

7.3 The integration gate shall execute the canonical cached submit → review → SSE → report → approver → redirect/gap path without AWS or Chroma, and shall assert its stable IDs, exact verdict composition, seeded provenance, ordering, approval behavior, and non-financial redirect semantics.

7.4 Before a task checkbox is marked complete, its focused validation shall pass. Python commands shall run with the repository `.venv` activated; changed Python must pass targeted pytest/Hypothesis and Ruff checks; frontend must pass targeted Vitest/property tests, strict TypeScript checking, and production Vite build. Browser/UI verification at 1366×768 shall be performed where browser tooling is available.

7.5 Completion reporting shall list changed files, exact validation commands and results, run instructions, and specific unresolved deferrals. It shall report only observed outcomes and blockers.

## Non-Functional Requirements

1. **Resilience:** Cached demo mode shall run fully offline except for optional map tiles and shall not require AWS, Bedrock, Chroma, or a local embedding-model download for the scripted flow.
2. **Security:** AWS credentials shall be sourced only from environment variables loaded from `agent/.env`; real secrets shall not be written to tracked files, responses, logs, or audit data. `.env.example` shall contain placeholders only.
3. **Performance:** Individual Bedrock operations shall have a 20-second timeout. Review stream progress shall be rendered within one second of receipt under normal browser operation.
4. **Accessibility and usability:** Controls, status, labels, errors, drawer focus behavior, and map information shall be keyboard-accessible or have accessible alternatives. The core dashboard shall remain usable at 1366×768.
5. **Maintainability:** Python shall use type hints, absolute package imports, Pydantic models, Ruff-compatible formatting/linting, and one documented agent tool per file. TypeScript shall remain strict with no `any`, functional React components, and hooks. Generated index artifacts shall remain rebuildable and git-ignored.
6. **Scope and operational safety:** No commit, push, git-history rewrite, or direct modification of raw source data is part of this work. Existing API ownership and port use must be respected.

## Acceptance Criteria

1. The repository contains validated shared Pydantic and strict frontend contracts for the stable pipeline/API/frontend IDs and all core proposal, review, verdict, memo, approval, gap, audit, and SSE payloads.
2. Project/need/proposal data preserves source provenance; seeded proposal/content is visibly labelled; illustrative or estimated need data is visibly labelled; missing snapshot provenance displays `TBD: needs source` rather than invented information.
3. The index builder validates rows, reports rejects, supports atomic incremental Chroma updates in `data/index/`, and the retrieval tests prove score bounds, ordering, uniqueness, `k <= 8`, and filter compliance.
4. Local embeddings operate without implicit network download in offline mode; Bedrock embedding/Nova failures time out at 20 seconds or produce readable typed failures; expired credentials produce HTTP 503 with `AWS credentials expired. Refresh agent/.env from Workshop Studio.`
5. The deterministic taxonomy tests prove that cross-city pairs cannot be `DUPLICATE`/`OVERLAPPING`, date/missing-date rules are conservative, duplicate evidence requires at least two attributes, and every final verdict has a valid label and confidence in `[0,1]`.
6. `POST /proposals`, review creation, review SSE, completed-report retrieval, approvals, audit retrieval, and `GET /gaps` operate through shared Pydantic models with documented validation/not-found/conflict/unavailable behavior.
7. A review stream has the ordered sequence `status → tool_call* → verdict* → (done | error)`, has exactly one terminal event, and no frontend state transition occurs after that terminal event.
8. The state machine permits only `SUBMITTED → REVIEWED → APPROVED|REJECTED`; only an approver may make the final transition; rejection with blank reason, repeated actions, skipped actions, and planner decisions are rejected without state mutation.
9. Audit tests prove that proposal/review/tool/verdict/downgrade/approval events record factual timestamped summaries without secrets, and approval tests prove no financial behavior is invoked.
10. In `DEMO_MODE=cached`, tests with failing AWS/Bedrock/retrieval mocks confirm none are called for the canonical review. The local cache parses successfully and returns exactly one `OVERLAPPING`, one `COMPLEMENTARY`, a seeded `CO_FINANCE` report, and a valid redirect district.
11. The cached smoke test executes proposal submission, review creation, ordered SSE events, report retrieval, approver action, audit lookup, and redirect/gap lookup without AWS or Chroma; it proves redirect focus changes no funding/need values.
12. `GET /gaps` returns sorted valid records, a known district filter returns one record, unknown districts return 404, and unavailable/malformed complete input returns readable 503 without recalculation or writes.
13. `frontend/` builds using React 18, Vite, strict TypeScript, Tailwind, Leaflet/react-leaflet, and exact pinned dependencies; the client’s REST/SSE tests prove request serialization, runtime validation, terminal cleanup, and readable error handling.
14. At 1366×768, the frontend presents a usable proposal panel, map, verdict list, and closed/open decision drawer; it displays textual verdict labels, confidence/reasoning/attributes, provenance, map selection, safe map-data fallback, and accessible controls.
15. The frontend canonical demo test and available browser smoke verification show a seeded proposal, exactly one `OVERLAPPING`, exactly one `COMPLEMENTARY`, `CO_FINANCE`, an approver-only decision, and a redirect focus explicitly described as non-financial.
16. The golden-pair evaluation supports quick and full modes, preserves provenance, includes at least twelve appropriately varied human-labelled pairs, and records factual evaluation output without claiming deployment accuracy.
17. Task checkboxes are updated only after their corresponding focused tests/checks pass; the final completion report records changed files, commands/results, run instructions, and precise remaining deferrals without commits, pushes, or git-history changes.

## Out of Scope

- Real money movement, payment processing, funding allocation, commitment changes, procurement actions, or claims that an approval/redirect funds a district.
- User authentication, production authorization infrastructure, multi-tenant deployment, or banking-system integration beyond the local Planner/Approver role toggle.
- Live scraping during the demonstration, modifying `data/raw/` by hand, or presenting unsourced/synthetic records as real-world evidence.
- A guarantee that Bedrock/Nova Pro is reachable in every workshop account; cached mode is the required demo fallback.
- Hosted vector databases, new frontend/state-management frameworks, unpinned dependencies, or technology outside the locked stack.
- Starting an additional FastAPI process on port 8000, committing/pushing changes, or altering git history.
- Claims of real-world outcome, aid effectiveness, citywide coverage, multi-funder coverage, or general accuracy beyond results demonstrably computed from sourced local data and the labelled evaluation dataset.
