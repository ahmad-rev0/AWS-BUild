# Design Review — Atlas11 MVP Completion

**Verdict: CHANGES_REQUESTED** — 2 HIGH and 3 MEDIUM findings.

## Findings

1. **HIGH — `GET /reviews/{review_id}` has two incompatible response contracts.**
   - **Where:** “FastAPI API and Error Model” endpoint table specifies success as `ClashReport`; “Frontend Architecture / VerdictCard” later specifies `ReviewReportResponse { report, candidates }` for the same endpoint.
   - **Problem:** A frontend implemented to the latter cannot parse the table’s former response. This violates the shared typed-contract requirement and leaves report retrieval, API response models, and SSE follow-up behavior ambiguous.
   - **Concrete fix:** Choose one contract and use it everywhere. For example:
     ```python
     class ReviewReportResponse(BaseModel):
         report: ClashReport
         candidates: list[ReviewCandidateDetail]

     @app.get("/reviews/{review_id}", response_model=ReviewReportResponse)
     def get_review(review_id: str) -> ReviewReportResponse: ...
     ```
     Update the endpoint table, frontend parser, smoke test, and acceptance tests to name `ReviewReportResponse`; do not describe this endpoint as returning a bare `ClashReport`.

2. **HIGH — The review execution/claim point conflicts with its stated errors and permits undefined concurrent stream behavior.**
   - **Where:** “Cached Demo Service” says cache parsing and review execution occur in `GET /reviews/{review_id}/events`; the API table assigns cache/provider failures to `POST /proposals/{proposal_id}/review` (503/502); the same section says a completed stream may replay or return a conflict, without choosing either.
   - **Problem:** These alternatives have materially different observable behavior. If `POST` only inserts a pending review, it cannot return a cache-validation 503. If two clients open the event endpoint while pending, the design does not define an atomic claim, so both can run providers/attempt completion and produce nondeterministic tool/audit events. A failed pending review also has no specified durable execution status or retry rule.
   - **Concrete fix:** Define and persist an execution state (`PENDING | RUNNING | COMPLETED | FAILED`) and a transactional `claim_review_execution(review_id)` operation. Specify one model, e.g. `POST` creates only `PENDING` (201); the first events request atomically claims it and emits any cache/provider failure as its single terminal `error`; concurrent requests receive 409 while `RUNNING`; `COMPLETED` replays the stored immutable event sequence; `FAILED` replays its stored terminal error (or explicitly permits a new review ID, not retry in place). Change the endpoint table to match that choice and add concurrent-consumer/error-order tests.

3. **MEDIUM — Canonical-ID validation is only a syntax check; the design never defines authoritative registries or when unknown city/district/project IDs are rejected.**
   - **Where:** “Shared Contracts and Persistence,” “Data Pipeline, Providers, and Retrieval,” and “Cached Demo Service.”
   - **Problem:** The existing `CanonicalContract` accepts any regex-shaped value; it does not prove a city or district exists. The design requires canonical filters and says cache parsing rejects unknown project/district IDs, but does not identify a project/district registry, the lookup function, or proposal/retrieval behavior for unknown city/district IDs. Consequently two valid-looking but nonexistent IDs can enter SQLite and make the cache/map flow fail late.
   - **Concrete fix:** Define a read-only registry boundary and its rules. For example: `load_district_registry()` loads the validated GeoJSON/need-score ID intersection; `load_project_registry()` loads validated processed plus seeded projects. `POST /proposals` returns 422 for a city/district absent from the relevant registry (except an explicitly documented city-only proposal); cached report validation returns 503 only for corrupted local cache references; live search with an unknown filter returns 422. State exactly how `city_id` is represented/validated, since current GeoJSON contains districts rather than a city registry.

4. **MEDIUM — Retrieval’s public filter contract is not fully specified.**
   - **Where:** “Data Pipeline, Providers, and Retrieval.”
   - **Problem:** The design says `SearchFilters` will add `sector` and use “inclusive implementation window,” but it never declares the final field names/types or whether a one-sided interval is supported. The current implementation exposes four distinct `approval_date_*`/`closing_date_*` filters, no `sector`, and permits `k` through 100. Multiple implementations could satisfy the prose yet filter different projects.
   - **Concrete fix:** Replace the prose with a single Pydantic input contract, e.g.:
     ```python
     class SearchRequest(BaseModel):
         query: str = Field(min_length=1, max_length=10_000)
         k: int = Field(ge=1, le=8)
         city_id: CanonicalId
         district_id: CanonicalId | None = None
         sector: str = Field(min_length=1)
         implementation_start: date | None = None
         implementation_end: date | None = None
     ```
     Require both dates when either is provided (or explicitly define one-sided semantics), map proposal dates to that interval, and state the exact metadata comparisons and 400/422 error response.

5. **MEDIUM — The deterministic cache’s proposal identity guard is not implementable from the design.**
   - **Where:** “Shared Contracts and Persistence” and “Cached Demo Service.”
   - **Problem:** The server is to assign `demo-proposal-01` only when input “matches the cached proposal identity/content guard,” and the cache is to contain a “proposal fingerprint/identity,” but neither the canonical proposal payload nor the fingerprint algorithm/canonical serialization is defined. Different whitespace, decimal/date JSON rendering, or an omitted optional field could yield incompatible guards; a loose implementation could let altered seeded content claim the fixed ID.
   - **Concrete fix:** Put an explicit `proposal: ProposalCreate` and `proposal_fingerprint` in the cache schema, define `fingerprint = sha256(json.dumps(proposal.model_dump(mode="json", exclude_none=False), sort_keys=True, separators=(",", ":")))`, and require exact model equality plus fingerprint equality before assigning `demo-proposal-01`. Return 422 for a nonmatching seeded canonical scenario and persist the cache’s canonical `ProposalCreate` rather than client text. Add tests for modified title, source, budget, dates, omitted optionals, and deterministic matching.

## Verified Assumptions

- `agent/app.py` currently exposes only `GET /gaps`, with typed `DistrictNeedRecord` output and 404/503 mapping for the gap boundary.
- `agent/store.py` already atomically creates proposals/reviews, atomically persists a completed report while transitioning `SUBMITTED → REVIEWED`, and sanitizes audit summaries. It does **not** currently enforce approver role inside `record_approval`, so the proposed defensive extension is necessary.
- `agent/schemas.py` currently rejects `Memo.redirect_district_id` unless recommendation is `REDIRECT`; the design correctly identifies the conflict with the required cached `CO_FINANCE` report and must change the validator as stated.
- `agent/embeddings.py` uses `SentenceTransformer(..., local_files_only=True)` for local embeddings and configures Bedrock connect/read timeouts of 20 seconds with retries disabled. `agent/errors.py` already defines the required credential-expiry message and maps the specified AWS error codes.
- `scripts/build_index.py` already validates processed and optional seeded CSV inputs independently, rejects duplicate IDs across accepted inputs, uses deterministic project hashes, reconciles incremental Chroma records, and atomically publishes the manifest after successful Chroma mutations.
- The five named deterministic tool files (`search_similar_projects.py`, `get_project.py`, `check_overlap.py`, `district_need.py`, and `draft_memo.py`) exist under `agent/tools/`.
- `agent/gaps.py` is a read-only loader that validates complete CSV rows, sorts by district ID, and maps missing/malformed data through typed errors; `scripts/build_need_scores.py` validates GeoJSON/indicator district-universe equality and atomically publishes need scores.

## Unverified/Wrong Assumptions

- **Wrong:** Current `agent/retrieval.py` does not meet the planned final retrieval contract: it permits `k` up to 100, has no `sector` filter, and exposes separate approval/closing date-bound fields rather than one defined implementation window. The design must specify the migration (Finding 4).
- **Wrong:** `scripts/check_aws.py`, `agent/clash_agent.py`, `data/demo_cache/`, and `frontend/` do not currently exist. They are valid planned additions, but must not be described as existing baseline assets.
- **Unverified by the design:** No authoritative city/district/project registry is identified for its “unknown cached project/district” and canonical-ID claims. Existing Pydantic canonical validation establishes format only, not existence (Finding 3).
- **Unverified by the design:** There is no specified persisted review execution state or event-sequence store to support the proposed completed-stream replay/terminal behavior (Finding 2).
