# Design Review — Atlas11 MVP Completion

## Verdict: CHANGES_REQUESTED

1. **HIGH — Cached candidate resolution is inconsistent with the proposed seeded-project source.**
   - **Where:** “Read-only canonical registries” and “Review orchestration and cached service” say cached candidates are held in `data/processed/seeded_projects.csv`; “Data pipeline” says `agent/registry.py` loads that file. But the design says `get_project`, `check_overlap`, and the other tools “continue,” without requiring them to use the registry. The actual `agent/tools/get_project.py` and `agent/tools/check_overlap.py` each read only `data/processed/projects.csv`; they cannot resolve a seeded candidate from the separate file. `agent/tools/search_similar_projects.py` also currently invokes retrieval without the design’s city/district/sector/date filters. Consequently, the canonical report cannot reliably populate `ReviewCandidateDetail` or deterministic facts for its seeded candidates.
   - **Concrete fix:** Make a single registry-backed project lookup mandatory for *all* tool and report resolution paths, and define the source precedence/error behavior. For example:
     ```python
     # agent/registry.py
     def get_registered_project(project_id: str) -> Project:
         return load_project_registry()[project_id]  # raise ProjectNotFoundError

     # agent/tools/get_project.py and check_overlap.py
     project = get_registered_project(project_id)
     ```
     Update `search_similar_projects` to accept the validated `SearchRequest`/proposal filter context, and add cached-mode tests proving both canonical candidate IDs resolve from `seeded_projects.csv`, including their provenance.

2. **HIGH — The lazy SSE execution design has no disconnect/cancellation recovery rule, so a claimed review can remain `RUNNING` forever.**
   - **Where:** “Baseline and chosen architecture,” “SQLite changes and invariants,” and “FastAPI and SSE contract.” The first SSE caller atomically changes `PENDING → RUNNING`; subsequent callers receive `409`; only normal completion/failure writes a terminal event. The design never defines what happens when that caller disconnects, the request task is cancelled, or serialization/yielding fails after the claim. That violates the required recoverable cached flow and can leave no consumer able to receive a terminal event or replay a report.
   - **Concrete fix:** Specify one durable execution policy and its transaction/error behavior. A minimal option that preserves lazy execution is:
     ```text
     execute_claimed_review(review_id) runs independently of the response iterator.
     It appends every event transactionally. In a broad finally/exception handler it calls
     fail_review(..., terminal_error) unless the review is COMPLETED; fail_review is idempotent
     and appends the sole terminal event. A reconnect during RUNNING receives the already
     persisted prefix and waits/polls for subsequent events rather than 409.
     ```
     Alternatively add a persisted lease with expiry and an atomic reclaim rule. Define which option is used, the client response while another executor owns the review, and tests for disconnect-before-terminal, executor exception, and exactly one terminal persisted event.

3. **MEDIUM — The canonical cache identity rule promises byte-level field-change rejection but the specified validation path cannot enforce it.**
   - **Where:** “Schema changes,” canonical fingerprint paragraph. The design says any changed title, optional null/omitted field, or other field must return `422`, but first parses requests as `ProposalCreate`, whose actual `model_config` has `str_strip_whitespace=True` and defaults `source="user"`; parsed model equality/fingerprints erase leading/trailing whitespace and cannot distinguish an omitted default from an explicitly supplied default. Therefore multiple requests the design describes as changed will be accepted as identical.
   - **Concrete fix:** Choose semantic canonical equality *or* define and implement an exact-wire identity contract. For exact-wire identity, validate a raw request object with required-key presence, reject unknown/missing/extra keys, and fingerprint a canonical JSON object that retains the presence policy before Pydantic normalization. For semantic equality, replace the contradictory sentence with: “Inputs are normalized by `ProposalCreate`; equivalent normalized payloads are accepted,” and list the normalized fields in the API contract. Add tests for whitespace and omitted-versus-explicit optional/default fields matching the selected rule.

4. **MEDIUM — Proposal provenance is not fully specified in the shared contract, despite a requirement to preserve available source URLs.**
   - **Where:** “Schema changes,” `CachedScenario`, and the frontend provenance presentation. The design requires proposal source provenance to be displayed and claims source URLs are preserved, but it does not add `source_url` to `ProposalCreate`/`Proposal` or state where a canonical seeded proposal’s URL is persisted. The actual `ProposalCreate` has `source` but no `source_url`, while existing golden-pair input already contains proposal-level `source_url` (currently ignored by the model). The frontend cannot truthfully display this provenance through `ReviewReportResponse`.
   - **Concrete fix:** Add an optional validated URL field to the shared proposal contract and carry it through cache, SQLite payloads, API responses, and TypeScript parsers:
     ```python
     class ProposalCreate(CanonicalContract):
         # ...
         source: Literal["seeded", "user"] = "user"
         source_url: str | None = None
     ```
     Define the seeded rule (for example, canonical cache requires `source_url="seeded://atlas11/demo-city-transit-01"`; user proposals may omit it), and add a frontend test that displays it when present.

5. **MEDIUM — Cached review preparation does not define the proposal/date representation needed by the existing deterministic overlap tool.**
   - **Where:** “CachedScenario” uses `proposal: ProposalCreate`; “Review orchestration and cached service” validates registries before execution; and “Read-only canonical registries” says the cache has a canonical proposal payload with ID `demo-proposal-01`. The actual `check_overlap` input requires a persisted `Proposal` with `proposal_id` and `submitted_at`, whereas `ProposalCreate` contains neither. The design does not say whether deterministic facts are evaluated against the persisted proposal, how the cache’s ID is represented without violating the cache schema, or whether cached reports avoid `check_overlap` altogether.
   - **Concrete fix:** Define the cache/persistence handoff explicitly. Prefer a cache contract with `proposal_id` and a `ProposalCreate` body, then construct the persisted `Proposal` once with server `submitted_at` before review execution:
     ```python
     class CachedScenario(BaseModel):
         scenario_key: Literal["demo-city-transit-01"]
         proposal_id: Literal["demo-proposal-01"]
         proposal: ProposalCreate
         # ...
     ```
     State that cache fingerprinting applies to `proposal`, and that deterministic tools receive `store.get_proposal(review.proposal_id)`. Add a test proving the cached report ID, stored proposal ID, `done` reference, and tool facts all use `demo-proposal-01`.

## Verified Assumptions

- `agent/app.py` currently exposes only `GET /gaps`, so the design correctly identifies the need to add the proposal, review, SSE, report, approval, and audit endpoints.
- `agent/schemas.py` is a Pydantic v2 shared contract boundary and already provides core `Proposal`, `Verdict`, `Memo`, `ClashReport`, approval, audit, and SSE models.
- The current `Memo` validator permits `redirect_district_id` only for `REDIRECT`; the design correctly identifies that this must change to support the required cached `CO_FINANCE` report with a map-focus target.
- `agent/store.py` currently has transactional proposal/review completion/approval persistence and audit sanitization, but no execution-status or persisted review-event table; the proposed additional lifecycle persistence is needed.
- `agent/gaps.py` is read-only and validates/sorts generated gap records. `scripts/build_need_scores.py` validates district-universe equality and atomically replaces the generated CSV, so retaining those boundaries is feasible.
- `agent/embeddings.py` uses `SentenceTransformer(..., local_files_only=True)` for local embeddings and constructs Bedrock clients with 20-second connect/read timeouts. `agent/config.py` reloads `agent/.env` on each `PipelineConfig.from_environment()` call.
- `scripts/build_index.py` already separates optional seeded input, validates rows, rejects duplicate IDs, uses deterministic hashes, removes stale IDs for incremental builds, and atomically publishes its manifest after index operations.
- `agent/clash_agent.py`, `scripts/check_aws.py`, `frontend/`, and `data/demo_cache/` do not currently exist, consistent with the baseline statement.
- The current local GeoJSON has only `district_id`; it lacks the proposed `district_name` and `city_id`. The design’s planned GeoJSON metadata update is therefore necessary. Existing need-score records are explicitly illustrative and use `TBD: needs source`.

## Unverified/Wrong Assumptions

- **Wrong:** The design implies existing project tools can continue while the canonical candidates reside in a separate seeded CSV. They cannot: both current project lookup and overlap checking load only `projects.csv`.
- **Wrong:** The proposed parsed-model fingerprint/equality check can distinguish every changed, null, or omitted submitted field. Pydantic normalization/defaulting in the actual `ProposalCreate` contract makes that impossible without a raw-payload presence contract.
- **Unverified:** No existing source supports the design’s claim that a Vite React plugin version is “matching” the listed frontend versions. Select and pin the exact `@vitejs/plugin-react` version in the implementation/lockfile rather than leaving “matching” as an unresolved dependency choice.
- **Unverified:** The design assumes an asynchronously claimed SSE review will continue to a terminal persisted state after a client disconnect. No current lifecycle/executor implementation exists, and the design does not yet supply the required cancellation/recovery behavior.
