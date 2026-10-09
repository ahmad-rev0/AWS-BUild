# Technical Design — Atlas11 MVP Completion

## Overview

Atlas11 will complete one reliable, local-first coordination workflow: a planner submits the fixed seeded proposal, the API creates a review, the first SSE consumer executes and streams a Pydantic-validated cached report, an approver records a coordination-only decision, and the map focuses a high-need district without modifying funding data. The FastAPI service is the sole lifecycle authority; SQLite is the durable audit/state boundary; React is a typed, untrusted-data client. The cached scenario (`demo-city-transit-01` / `demo-proposal-01`) is the integration gate and must run without AWS, Bedrock, Chroma, or a downloaded embedding model. Live retrieval and Nova Pro are constrained secondary paths.

The locked stack is Python 3.11+, FastAPI/Uvicorn, Pydantic v2, SQLite, Strands Agents SDK, ChromaDB, Bedrock Nova Pro/Titan V2, and React 18 + Vite + strict TypeScript + Tailwind + Leaflet/react-leaflet. The frontend will pin `react@18.3.1`, `react-dom@18.3.1`, `vite@5.4.10`, `typescript@5.6.3`, `tailwindcss@3.4.14`, `leaflet@1.9.4`, `react-leaflet@4.2.1`, `@types/leaflet@1.9.12`, `vitest@2.1.3`, `@testing-library/react@16.0.1`, `@testing-library/user-event@14.5.2`, `@testing-library/jest-dom@6.6.3`, `fast-check@3.23.1`, and the matching pinned Vite React plugin. No state-management, component, map, or hosted-database framework will be introduced.

## Baseline and chosen architecture

Existing `agent/schemas.py`, `agent/store.py`, `agent/gaps.py`, `scripts/build_need_scores.py`, `scripts/build_index.py`, `agent/config.py`, and `agent/embeddings.py` provide the starting contracts and boundaries. `agent/app.py` currently only exposes `GET /gaps`; `frontend/`, `agent/clash_agent.py`, `scripts/check_aws.py`, and demo-cache records do not exist. The implementation will extend rather than bypass the established Pydantic/SQLite/gap boundaries.

The API will execute a review lazily on the first event-stream request, rather than in the review-creation request. This is chosen because it makes visible SSE progress deterministic and avoids background-process requirements. To remove concurrency ambiguity, review execution state and immutable event records are persisted. `POST /proposals/{proposal_id}/review` only creates a `PENDING` review; the first `GET /reviews/{review_id}/events` atomically claims it as `RUNNING`; concurrent consumers receive `409`; completed and failed reviews replay their persisted event sequence. This explicitly resolves cache/provider error timing: runtime cache/provider failures are emitted as the stream’s sole terminal `error`, not returned by the POST.

## Shared contracts, registries, and persistence

### Schema changes

`agent/schemas.py` will remain the source of truth and gain the following models/enums:

- `ReviewExecutionStatus = PENDING | RUNNING | COMPLETED | FAILED` and `ReviewStatusResponse` for lifecycle inspection when needed by tests/internal services.
- `SearchRequest` with `query: str` (trimmed 1–10,000 chars), `k: int` (1–8), required `city_id`, optional `district_id`, required trimmed `sector`, and `implementation_start` / `implementation_end` (`date | None`). Both dates are required together when either is supplied; `end < start` is invalid. A proposal with incomplete dates supplies no time filter, rather than inventing a one-sided range.
- `ReviewCandidateDetail` containing a `Verdict` and resolved `Project`; `ReviewReportResponse { review_id, proposal: Proposal, report: ClashReport, candidates: list[ReviewCandidateDetail] }`. This is the **only** successful `GET /reviews/{review_id}` contract. It lets the dashboard show identity/funder/provenance without inventing project details from verdicts.
- `ReviewEventRecord` (sequence, `SseEvent`, UTC timestamp) for persistence and deterministic replay, plus `ApiErrorResponse { error: str }`.
- A cache-only `CachedScenario` contract with `scenario_key`, exact `proposal: ProposalCreate`, `proposal_fingerprint`, `report: ClashReport`, and a bounded ordered list of scripted tool/status metadata. It validates `report.source == "seeded"`, report proposal ID matching, exactly two unique verdict project IDs, one `OVERLAPPING`, one `COMPLEMENTARY`, `memo.recommendation == CO_FINANCE`, and a non-null canonical `redirect_district_id`.

The current `Memo` rule that permits a redirect district only for `REDIRECT` conflicts with the required `CO_FINANCE` cached report. It will be changed to permit `redirect_district_id` only for `CO_FINANCE` or `REDIRECT`; in both cases the field is explicitly a coordination/map-focus target, never a financial instruction. `ClashReport` also validates unique candidate project IDs. `ApprovalCreate` trims `reason` before enforcing the rejection requirement. All incoming request, persisted payload, tool input/output, cached record, API response, and streamed event types remain Pydantic validated.

The canonical demo fingerprint is exactly:

```python
sha256(
    json.dumps(
        proposal.model_dump(mode="json", exclude_none=False),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()
```

When `source=seeded` and `scenario_key=demo-city-transit-01`, `POST /proposals` must load the cache first, parse it, compare the submitted `ProposalCreate` by model equality and fingerprint, and persist the cache’s canonical proposal payload with ID `demo-proposal-01`. Any changed title, description, source, budget, date, optional null/omitted field, or other field returns `422` and creates no row. A normal `source=user` proposal gets a generated stable ID and may not claim that scenario key.

### Read-only canonical registries

Syntax-valid IDs alone are insufficient. `agent/registry.py` will provide explicit read-only registry boundaries:

- `load_project_registry()` validates and loads `data/processed/projects.csv` plus optional `data/processed/seeded_projects.csv`, rejecting conflicting IDs through the existing pipeline rules, then returns `project_id -> Project`.
- `load_district_registry()` validates `data/geo/districts.geojson` and `agent.gaps.load_gap_records()`, requiring an identical district-ID universe. Each GeoJSON feature must contain `district_id`, `district_name`, and `city_id` canonical properties. It returns district records and `district_id -> city_id`.
- `load_city_registry()` is the deterministic union of non-empty `Project.city` values and GeoJSON `city_id` values. Existing sourced project city strings are opaque canonical values; no display-name normalization or geocoding is performed.

The seeded GeoJSON/indicator/demo-project records will use `atlas11-demo-city`, with the two existing demo district IDs associated to it. This is seed/illustrative data and remains visibly labelled as such. Submission rejects an unknown `city_id` with `422`; a supplied `district_id` must exist and belong to that city or also returns `422`. City-only proposals are valid when the city is in the city registry. Live `SearchRequest` performs the same validation. Cache references to unknown project/district IDs are local-data corruption and return a readable `503` from the event stream; they are never silently removed or matched by name.

### SQLite changes and invariants

`agent/store.py` will migrate the local schema safely with `CREATE TABLE IF NOT EXISTS` and additive columns/tables. `reviews` gains `execution_status`, `failure_message`, and `updated_at`; a `review_events` table stores `(review_id, sequence)` as its primary key with serialized validated event JSON and timestamp. A unique review-per-proposal constraint is retained through the existing proposal lifecycle guard. The repository adds:

```python
create_review(...) -> ReviewCreated                 # PENDING only
claim_review_execution(review_id) -> Proposal       # PENDING -> RUNNING atomically
append_review_event(review_id, event) -> ReviewEventRecord
complete_review(...) -> ClashReport                  # RUNNING -> COMPLETED + SUBMITTED -> REVIEWED atomically
fail_review(review_id, message, terminal_event, audits) -> None  # RUNNING -> FAILED atomically
get_review_execution(review_id) -> ReviewExecutionStatus
list_review_events(review_id) -> list[ReviewEventRecord]
get_review_context(review_id) -> Proposal
```

`claim_review_execution` uses `BEGIN IMMEDIATE` and `UPDATE ... WHERE execution_status='PENDING'`; exactly one caller can execute. `complete_review` accepts only `RUNNING`, validates that the report proposal matches the review, persists report/status/audits in one transaction, and requires that the final stored event is `done`. `fail_review` preserves `SUBMITTED`, records only one terminal `error`, and never writes a report. A failed review cannot be rerun in place; the planner must submit a new proposal/review after correction. A completed review is immutable and event replay does not append audits.

`record_approval` must defensively reject `role != APPROVER` before any status update, not rely on FastAPI alone. It permits only a report-bearing `COMPLETED` review and proposal state `REVIEWED`; it atomically writes approval, `APPROVED`/`REJECTED`, and audit. No persistence method receives a payment, allocation, commitment-change, or transfer dependency.

Audit summaries are sanitized by the existing secret redactor and capped. The service appends proposal submitted, review created/claimed, every generated tool call, every emitted verdict, taxonomy downgrade, completion/failure, denied approval attempt, and successful decision records with UTC timestamp, actor/role where available, canonical IDs, and factual short text. Replay requests generate no duplicate lifecycle audit events.

## Data pipeline, providers, retrieval, and diagnostics

`agent/retrieval.py` will replace its public `TypedDict` filter surface with `search(request: SearchRequest) -> list[Candidate]`. It validates registry membership before opening Chroma. It queries the local collection, applies exact `city`, optional exact `district`, exact case-folded `sector`, and one inclusive implementation interval. With a supplied interval `[start, end]`, a project is eligible only when it has a valid `[approval_date, closing_date]` and `project.approval_date <= end and project.closing_date >= start`. Missing/malformed dates are excluded from a date-constrained request. The returned list is unique, normalized to `[0,1]`, ordered by `(-score, project_id)`, and capped at eight. Invalid query/filter input raises `SearchInputError`, which the API maps to `422`; unavailable Chroma/provider is a readable `503`/stream error depending on call context. The clash service maps proposal dates only when both are known.

`agent/tools/search_similar_projects.py` takes its Pydantic input, constructs this exact request, and returns IDs/scores only. It retrieves at most eight, then `agent/clash_agent.py` deterministically resolves and passes at most five packages to the model. `get_project`, `check_overlap`, `district_need`, and `draft_memo` continue as one documented tool per file. `check_overlap` remains the owner of canonical geography, exactly-12-calendar-month slack, conservative missing-date logic, concrete-output evidence, and beneficiary facts; the model never calculates these facts.

`agent/embeddings.py` already uses cached-only MiniLM and 20-second Bedrock connect/read timeouts. It will be covered with fakes to prove no implicit download/AWS call in local mode. Each live provider request reloads `agent/.env` through `PipelineConfig.from_environment()` and creates a fresh boto3 session. Bedrock `ExpiredTokenException`, `UnrecognizedClientException`, and `ExpiredToken` map to `CredentialsExpired`; FastAPI returns precisely `503 {"error":"AWS credentials expired. Refresh agent/.env from Workshop Studio."}` for non-streaming operations and an SSE `error` payload with the same readable text for an already-created review. Secrets never enter logs, errors, cache, or audit.

`scripts/build_index.py` retains its current per-row validation, deterministic SHA-256 content hash, optional seeded-file boundary, stale record removal, and post-Chroma atomic manifest publication. Its tests will verify no invalid/duplicate row is indexed and that changed metadata re-upserts. `scripts/check_aws.py` will load current dotenv values, independently invoke the configured Nova Pro and Titan IDs with 20-second bounded clients, report model ID/callability/token lifetime when introspectable, and exit non-zero when either check is unavailable. It never prints credentials or tokens.

## Review orchestration and cached service

`agent/prompts/clash_system.md` will contain the concise four-label taxonomy, conservative evidence rule, structured `ClashReport` JSON instruction, non-financial coordination language, and tool-use constraints, under the prompt token budget. `agent/clash_agent.py` contains exactly one lazily constructed Strands `Agent`; it loads this file, creates the configured Nova Pro model from freshly loaded configuration, and uses the five tools. It runs live calls with a hard 20-second timeout, parses the result as `ClashReport`, retries once with Pydantic validation feedback, applies taxonomy post-processing only after validation, and raises a readable invalid-output error after the second failure.

The taxonomy post-processor resides in `agent/taxonomy.py`. It deduplicates fact-backed matching attributes, enforces city/date/district limits, requires concrete-output evidence plus at least two matching attributes for `DUPLICATE`, downgrades insufficient duplicates to `OVERLAPPING` with an audit event, and bounds confidence. Different cities can only become `COMPLEMENTARY` (when sector evidence supports a relationship) or `UNRELATED`; same-city/different-district pairs can be `OVERLAPPING` only with explicit shared beneficiaries; unknown/missing dates cannot establish `DUPLICATE` or `OVERLAPPING`. Evidence insufficiency always selects the less severe allowable label.

`agent/demo_cache.py` will resolve only the canonical scenario from `data/demo_cache/demo-city-transit-01.json`. It reads UTF-8 JSON, validates `CachedScenario`, checks fingerprint and registries before execution, and returns a typed cache error without invoking the agent, retrieval, embeddings, Chroma, boto3, or AWS diagnostics. The cache includes the seeded canonical proposal, report, referenced seeded project records (in the separate seeded project CSV), and a scripted status/tool ordering. It must produce exactly:

1. a non-blank `status`,
2. zero or more scripted `tool_call` entries with non-negative duration,
3. one `OVERLAPPING` verdict and one `COMPLEMENTARY` verdict,
4. a single `done` event referencing the same review ID.

The `CO_FINANCE` memo names the redirect district only as a coordination-focus recommendation. Approval changes only the proposal decision state; map focus is derived from the already-persisted report and does not write need or funding data.

## FastAPI and SSE contract

`agent/app.py` will add an application factory/configurable dependencies for test isolation, retain port ownership outside the application, and expose these endpoints. API failures use `ApiErrorResponse`; FastAPI request validation is converted to a concise `422` error response rather than a stack trace.

| Endpoint | Success | Failure behavior |
|---|---|---|
| `POST /proposals` | `201 Proposal` | `422` malformed/unknown city/district or noncanonical cache identity; `409` existing ID; no durable write on failure. |
| `POST /proposals/{proposal_id}/review` | `202 ReviewCreated` with a new `PENDING` review | `404` missing proposal; `409` not `SUBMITTED`/already reviewed; no provider/cache work occurs here. |
| `GET /reviews/{review_id}/events` | `text/event-stream` | `404` unknown; first `PENDING` caller claims/runs; `RUNNING` concurrent caller gets `409`; `COMPLETED`/`FAILED` replays immutable stored events. Runtime failure emits `status` then exactly one terminal `error` and persists `FAILED`. |
| `GET /reviews/{review_id}` | `200 ReviewReportResponse` only after completed | `404` unknown; `409` pending/running/failed/no validated report. |
| `POST /approvals` | `201 Approval` | `403` planner role; `422` blank rejection reason/bad IDs; `404` review absent; `409` skipped/repeated/failed review; unchanged status on every denial. |
| `GET /audit` | sorted `list[AuditEvent]` | `422` invalid filters; no credentials/raw secrets. |
| `GET /gaps?district_id=` | sorted list or one `DistrictNeedRecord` | `404` unknown valid district; `503` missing/malformed complete data; read-only/no recalculation. |

SSE serialization is `event: review\ndata: <SseEvent JSON>\n\n`. For a successfully claimed review, the server appends/persists and yields `status → tool_call* → verdict* → done`; for a failure it emits `status → tool_call* → error`, with one and only one terminal event. The `done.payload` is `{ "review_id": id }`, never an unvalidated report. The frontend fetches `GET /reviews/{id}` after `done`. Stored replay maintains original sequence/durations and performs no model work.

The service logs expected operational failures at warning level with IDs and exception class only; unexpected exceptions are logged server-side with request/review correlation IDs but response bodies remain generic. Cache corruption, provider failure, model schema failure, tool failure, and timeout are recoverable from the product perspective because cached mode or a new review remains available; malformed local gap data is recoverable after data repair but fatal for map/gap rendering; database write failure is fatal to the current operation and returns `503`/stream `error` without claiming completion.

## Frontend architecture

`frontend/` will be created with `package.json`, `package-lock.json`, `vite.config.ts`, strict `tsconfig.json`, Tailwind/PostCSS config, `index.html`, and `src/`. Vite serves on 5173. The API base URL comes from `VITE_API_BASE_URL` (default `http://localhost:8000`) and development CORS is explicitly allowed by FastAPI only for the Vite origin. The API process on 8000 is externally managed and must not be started by frontend setup or tests.

- `src/types/contracts.ts` mirrors every API enum/model, including `ReviewReportResponse`, gap/audit data, and opaque canonical IDs.
- `src/types/parsers.ts` contains manual type guards/parser functions for every REST body and SSE event. Unknown enum values, non-finite confidence/duration, invalid source, malformed dates, and unexpected fields where contract-sensitive cause `ApiError("Incompatible API response")`; no state is updated.
- `src/api/clashApi.ts` implements typed fetch methods for all dashboard endpoints. It parses `ApiErrorResponse`, maps the exact credential 503 string to `kind: "credentials-expired"`, and otherwise exposes a readable status/detail. `src/api/sse.ts` uses cancellable `fetch` plus `ReadableStream` parsing (instead of EventSource) so an `AbortController` reliably stops the stream; it validates every event and closes itself on the first terminal event.
- `src/hooks/useReviewWorkflow.ts` owns a reducer with `idle`, `submitting`, `creating-review`, `streaming`, `complete`, and `error`. It retains draft form values on any failed submission, accepts event state only until the first terminal event, fetches the canonical `ReviewReportResponse` only after `done`, aborts on unmount/retry, and stores map focus separately from gap records. It exposes approval only when role/status/report/review ID make it valid.
- `src/pages/PlannerDashboard.tsx` composes the dashboard. `src/components/ProposalForm.tsx`, `RoleToggle.tsx`, `SeededBadge.tsx`, `VerdictCard.tsx`, `MapWorkspace.tsx`, `GapCallout.tsx`, `MemoPanel.tsx`, `AgentTrace.tsx`, and `DecisionDrawer.tsx` own accessible presentation. `src/utils/format.ts` handles money/provenance/snapshot display without altering received precision.

At 1366×768, Tailwind layout is a fixed 360px internally-scrollable left proposal/verdict panel, a flexible central map, and a right drawer closed by default. The drawer overlays the map rather than collapsing the left panel, traps focus while open, closes with Escape, and returns focus to its trigger. Streaming always shows a meaningful stage (“Review started”, “Searching comparable projects”, “Checking deterministic overlap facts”, or “Preparing coordination memo”), never a blank spinner. The map center stays usable when the drawer is open.

`MapWorkspace` loads copied/static `districts.geojson` and `need_scores.csv` from `frontend/public/data/geo/` at build/dev serving time; the implementation copies these generated/local assets through a documented build preparation script rather than reading filesystem paths in the browser. It validates the GeoJSON/CSV intersection and renders an accessible sequential need-score choropleth, legend, popup, and visible indicator-quality/snapshot legend. It labels `estimated` and `illustrative` records explicitly; unknown snapshots render `TBD: needs source`. OpenStreetMap tiles are optional; asset/map load failure renders a localized map-unavailable panel while intake, reports, and approvals still work.

Project/candidate coordinates are an optional local, provenance-labelled lookup keyed by canonical IDs. A project without coordinates is still rendered in its verdict card but has no fabricated marker/line. The proposal pin, resolved project pins, selected highlight, and proposal-to-candidate lines render only with both endpoints. The four required colors are always paired with text: `DUPLICATE #C0392B`, `OVERLAPPING #D68910`, `COMPLEMENTARY #138D75`, `UNRELATED #7F8C8D`. Verdict cards show label, confidence, fact-backed attributes, reasoning, resolved project identity/funder/amount, provenance, and a map-select action.

`SeededBadge` is shown if and only if a proposal, report, or project source is `seeded`. The memo drawer says “coordination sign-off” and “coordination focus” in all approval/redirect copy. Approve/Reject appears only to `approver` with a final `REVIEWED` proposal and persisted report; planner users receive an explanatory message. Reject requires non-whitespace input. The redirect action calls only `focusDistrict(id)` and must not mutate the gap array, need score, commitments, per-capita value, or funding-gap classification.

## File-level implementation plan

| Area | Files to modify/create |
|---|---|
| Contracts/errors | Modify `agent/schemas.py`, `agent/errors.py`; create `agent/registry.py`, `agent/taxonomy.py`, `agent/demo_cache.py`. |
| State/API | Modify `agent/store.py`, `agent/app.py`; create/extend API, store, SSE, and cache tests in `agent/tests/`. |
| Agent | Create `agent/clash_agent.py`, `agent/prompts/clash_system.md`; complete the five files in `agent/tools/` and their tests. |
| Pipeline | Modify `agent/retrieval.py`, `agent/config.py`, `agent/embeddings.py`, `scripts/build_index.py`; create `scripts/check_aws.py`; add focused provider/retrieval/index tests. |
| Demo/data | Create `data/demo_cache/demo-city-transit-01.json`, `data/processed/seeded_projects.csv`, demo coordinate data, and registry-required GeoJSON city properties; keep raw data unchanged and label all seed/illustrative records. |
| Gaps | Retain `agent/gaps.py` read-only; modify `scripts/build_need_scores.py`/GeoJSON inputs only for explicit city registry metadata and preserve atomic publication; add regression tests. |
| Evaluation/smoke | Modify `agent/eval.py`/golden-pair data only to meet the labelled-pair requirements; create `scripts/demo_smoke.py` and focused integration tests. |
| Frontend | Create the complete `frontend/` Vite application, tests, exact lockfile, public geo assets, and no additional framework. |

## Test and validation strategy

Python unit tests use fakes for Chroma, boto3, Strands, cache paths, and temporary SQLite databases. They cover Pydantic cache fingerprint equality, registry unknown-ID behavior, schema/date/provenance validation, taxonomy boundary/downgrade logic, read-only gaps, index reconciliation, retrieval ordering/filter soundness, credential mapping, atomic lifecycle/approval/audit operations, cached isolation with AWS/retrieval mocks that fail if called, live retry/timeout behavior, and exact error envelopes. Hypothesis properties prove overlap symmetry, cross-city exclusion, duplicate evidence minimum, bounded taxonomy closure, approval reachability, SSE terminal exclusivity, retrieval uniqueness/order/filter compliance, and no map-state funding mutation on redirect.

FastAPI integration tests execute submit → PENDING review → first SSE claim → ordered events → `ReviewReportResponse` retrieval → approver approval → audit → gap lookup. They separately assert concurrent event consumers receive `409`, `COMPLETED` and `FAILED` reviews replay stored events without rerunning execution, invalid cache leaves a proposal `SUBMITTED`, and no cache scenario calls AWS/Chroma. `scripts/demo_smoke.py` uses `DEMO_MODE=cached`, a temporary/local database, and the public API contract to assert `demo-proposal-01`, exactly one `OVERLAPPING`, exactly one `COMPLEMENTARY`, `CO_FINANCE`, seeded provenance, approver-only transition, and unchanged gap funding/need values after focus.

Vitest and React Testing Library cover parsers/transport, request shape/error mapping, stream abort and terminal immutability, reducer lifecycle, form retention, seeded badge iff source, all verdict card labels, role/decision availability, rejection validation, drawer keyboard behavior, map fallback, missing-coordinate omission, and redirect focus. fast-check covers accepted stream terminal safety, approval state combinations, verdict presentation closure, seeded provenance, and redirect immutability. A mocked canonical frontend flow executes submit → SSE → report → Approver → approve → redirect focus. If browser tooling is available, the checked UI smoke runs at 1366×768 with drawer closed/open and keyboard traversal.

Required validation commands after implementation are targeted and run with `.venv` activated: `pytest` for changed contract/store/API/cache/retrieval/gap/smoke tests, `ruff check` and `ruff format --check` on changed Python, `python -m agent.eval --quick`, and `python scripts/demo_smoke.py` with `DEMO_MODE=cached`. Frontend validation is `npm test -- --run` for changed tests, `npm run typecheck`, and `npm run build`. Task checkboxes are updated only when the corresponding command passed; the final report records observed output only.

## Operational boundaries and deferrals

Run the API only when port 8000 is free; for this task, reuse the externally managed API already on 8000. Run the frontend with `cd frontend && npm run dev -- --port 5173`; cached API mode uses `DEMO_MODE=cached` and does not require AWS or Chroma. A live review requires valid current `agent/.env` credentials, a workshop-accessible configured Nova Pro/Titan ID, Chroma, and the local index. If these are unavailable, the API exposes a typed readable failure and the cached canonical scenario remains the supported demo route.

No feature will create, simulate, or claim a payment, allocation, commitment increase, or funds delivered to a district. Source URLs are preserved; seeded material carries `source=seeded` and UI badges; illustrative/estimated need indicators and missing snapshot dates are explicit. Live account reachability, downloading/cache-warming MiniLM, rebuilding a full production index, and browser verification unavailable in the execution environment are operational deferrals only after the offline cached smoke path passes.

## Design-review finding responses

1. **Addressed — single report contract.** `GET /reviews/{review_id}` is defined exclusively as `ReviewReportResponse`; endpoint, parser, tests, smoke path, and dashboard use that envelope, never a bare `ClashReport`.
2. **Addressed — deterministic execution ownership.** The design adds persisted `PENDING/RUNNING/COMPLETED/FAILED`, transactional claim, one terminal stored event, `409` for a concurrent RUNNING stream, and immutable completed/failed replay. Cache/provider errors occur in the stream after a `status`, consistently with lazy execution.
3. **Addressed — authoritative registries.** `agent/registry.py` validates project, district, and city registries; submission/search/cache have specified unknown-ID handling, and GeoJSON receives explicit canonical `city_id` properties.
4. **Addressed — exact retrieval input.** `SearchRequest` fixes names, types, `k <= 8`, both-or-neither date rule, interval predicate, sector semantics, and `422` error behavior.
5. **Addressed — implementable demo identity guard.** `CachedScenario` contains the canonical `ProposalCreate` and the exact SHA-256 canonical JSON procedure; cache assignment requires model equality plus fingerprint equality and tests altered/omitted fields.
