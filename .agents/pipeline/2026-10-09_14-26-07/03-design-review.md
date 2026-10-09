# Design Review — Atlas11 MVP Completion

## Verdict: CHANGES_REQUESTED

1. **HIGH — The canonical seeded provenance URL cannot validate with the specified Pydantic type.** In **Shared contracts, provenance, registries, and cache identity**, the design adds `source_url: HttpUrl | None` but requires `source_url="seeded://atlas11/demo-city-transit-01"`. Pydantic v2 `HttpUrl` accepts only `http` and `https`; direct validation with the repository’s installed Pydantic 2.14.0 rejects this value with “URL scheme should be 'http' or 'https'.” This makes canonical cache intake impossible. **Fix:** choose one consistent contract. For example, use `source_url: str | None` with a validator allowing either `http(s)` URLs or the exact `seeded://atlas11/demo-city-transit-01` URI (and label the latter as non-link provenance), or use `https://atlas11.local/demo-city-transit-01` if `HttpUrl` must be retained. State the accepted schemes in the schema design and frontend parser.

2. **HIGH — The SQLite schema evolution is unspecified and will fail against the existing database.** In **Chosen architecture and durable review execution**, the design says it “adds” `execution_status`, `failure_message`, `execution_lease_expires_at`, and `updated_at` to `reviews`, plus `review_events`, but gives no migration/versioning procedure. The actual `agent/store.py` currently creates `reviews(review_id, proposal_id, report_json, source, created_at, completed_at)` only and uses `CREATE TABLE IF NOT EXISTS`; it will not add columns to the already-created `data/atlas11.db`. New claim/lease queries would therefore fail at runtime, including in the required cached demo. **Fix:** define an idempotent migration run by `SQLiteStore.initialize()` before serving requests, e.g. a `schema_migrations` table and numbered migration that uses `PRAGMA table_info(reviews)` then `ALTER TABLE ... ADD COLUMN` for each missing field, creates `review_events`/indexes, backfills `execution_status` (`COMPLETED` when `report_json IS NOT NULL`, otherwise `PENDING`), and executes in one transaction. Include a migration test starting from the current schema fixture.

3. **MEDIUM — The SSE wire schema remains under-specified and does not meet the stated typed-payload boundary.** In **Cached review, API, audit, and errors**, the design says each stream payload is a validated `SseEvent JSON`, but it only describes `SseEvent` generically and gives `done.payload` as an untyped object. The current `agent.schemas.SseEvent` has `payload: dict[str, object] | None` and does not require a status message, tool name/duration pairing, a typed verdict payload, or the required `review_id` in `done`; unknown nested payload keys/enums can therefore reach the frontend. This conflicts with requirement 1.2 and 4.3. **Fix:** specify a discriminated union for event payloads and validation rules, for example:

```python
class StatusPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=500)

class DonePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    review_id: str

class ToolCallEvent(BaseModel):
    type: Literal["tool_call"]
    name: Literal["search_similar_projects", "get_project", "check_overlap", "district_need", "draft_memo"]
    ms: int = Field(ge=0)
    payload: None = None
```

Define equivalent `status`, `verdict`, `done`, and `error` variants, forbid extras at every nested level, and mirror this exact union in TypeScript parsers. State whether the `error` payload has a stable `code` and `message` shape.

4. **MEDIUM — Lease ownership/reclamation is not implementable from the listed store signatures.** In **Chosen architecture and durable review execution**, `claim_or_observe_review(review_id, now) -> ClaimResult`, `renew_review_lease(review_id, now) -> None`, and `complete_review(...)` are listed, while completion is said to accept only the *owning* `RUNNING` review. No owner token, lease duration, returned lease expiry, or ownership parameter is defined. Two workers can otherwise both see/renew a `RUNNING` row or a reclaimed worker can complete after a new owner claims it. **Fix:** define an opaque per-execution token and exact lease semantics, e.g. `claim_or_observe_review(..., lease_seconds=30) -> ClaimResult(owner_token, lease_expires_at, started)`; persist `execution_owner_token`; require that token and `execution_lease_expires_at > now` in `renew_review_lease`, `append_review_event`, `complete_review`, and `fail_review` update predicates. Return a conflict/no-op result when ownership is lost, and test stale-worker completion after reclaim.

5. **MEDIUM — The contract for the project/city registry is inconsistent with current data models and lacks its required canonical-ID mapping.** In **Shared contracts, provenance, registries, and cache identity**, `load_city_registry()` is defined as the union of project `city` values and GeoJSON `city_id` values, and proposal creation validates `city_id` membership. The current `Project` contract has `city` and `district` display-like fields, but no `city_id`; the current Chroma metadata also stores `city`/`district`, not canonical `city_id`/`district_id`. Merely unioning those strings neither defines equivalence nor ensures `district_id` belongs to a canonical city, so valid seeded input may be rejected or geography comparisons may fall back to incompatible representations. **Fix:** extend the normalized project contract and CSV/index metadata with required canonical `city_id` and optional canonical `district_id` (keep display names separately), and define district GeoJSON properties as `district_id`, `city_id`, and display names. Make `load_city_registry()` return only canonical `city_id` values; validate `proposal.district_id` against the district registry’s `city_id`; use these IDs exclusively for retrieval filters and taxonomy.

6. **MEDIUM — The proposed live-retrieval filter rules do not define the required proposal-to-project date mapping.** In **Retrieval, providers, taxonomy, and live agent**, `SearchRequest` is described as having a `[implementation_start, implementation_end]`, while the existing index and retrieval implementation use project `approval_date`/`closing_date` fields and four differently named filter bounds. The design says it will apply an “inclusive implementation intersection” but never states which persisted project fields form the interval, whether the 12-month slack applies at retrieval or only taxonomy, or the exact Chroma/post-filter predicate. This leaves multiple valid implementations and risks different candidates reaching the agent. **Fix:** define one common interval vocabulary and conversion rule, e.g. `Project.implementation_start = approval_date`, `Project.implementation_end = closing_date` for current normalized inputs; retrieval prefilter uses the proposal’s unexpanded inclusive interval, excludes projects with either bound absent, and taxonomy alone applies the exact ±12-calendar-month slack. Rename/index metadata accordingly or explicitly map the legacy field names, and add boundary examples/tests.

7. **NIT — The design overstates capabilities of the existing index builder rather than distinguishing planned work.** In **Retrieval, providers, taxonomy, and live agent**, it says “The existing index builder remains responsible” for separate seeded input, deterministic hashes, stale deletion, and atomic manifest publication. Those parts are mostly present in `scripts/build_index.py`, but the current builder mutates the live Chroma collection before publishing its manifest; if `upsert` or `delete` partly fails, the manifest is preserved but the collection may already be changed. **Fix:** reword this as planned reconciliation work and specify recovery: either build a staging collection and atomically switch an active-collection pointer/manifest, or document and test a deterministic repair/rebuild path when collection mutation fails.

## Verified Assumptions

- `agent/app.py` currently exposes only `GET /gaps`; the design correctly treats proposal, review, SSE, approval, audit, and application-factory work as implementation to add rather than an available API.
- `agent/store.py` is the current SQLite persistence boundary and already uses `BEGIN IMMEDIATE` for mutating methods. It currently persists proposals, reviews, approvals, and audits, so extending it as the sole writer is feasible.
- `agent/gaps.py` is a read-only validated CSV loader. It returns district records sorted by ID, returns typed unavailable/not-found errors, and does not write/recalculate during reads, consistent with retaining it as a read-only gap boundary.
- `scripts/build_index.py` already validates `projects.csv` and optional `seeded_projects.csv`, rejects duplicate IDs, produces deterministic content hashes, supports an incremental manifest, and atomically replaces the manifest file.
- `agent/embeddings.py` already instantiates local `SentenceTransformer` with `local_files_only=True`; the design’s no-implicit-download local embedding behavior is supported by the current implementation.
- `agent/config.py` reloads `agent/.env` via `PipelineConfig.from_environment()` and `BedrockEmbeddingProvider` creates a fresh boto3 session when instantiated. The proposed per-request construction can therefore meet credential refresh requirements.
- `agent/errors.py` defines the exact required credential-expiry message and maps `ExpiredToken`, `ExpiredTokenException`, and `UnrecognizedClientException` to `CredentialsExpired`.
- No `frontend/` application exists in the repository at review time, so creating it is necessary and does not conflict with an existing frontend implementation.

## Unverified/Wrong Assumptions

- **Wrong:** `HttpUrl` can represent the required `seeded://` source URI. The installed Pydantic version rejects it, as described in Finding 1.
- **Unverified:** The existing `data/atlas11.db` can accept the proposed review-execution fields. Current initialization contains no migration mechanism; this must be implemented and tested before that assumption is valid.
- **Unverified:** Current processed project and GeoJSON assets contain a compatible canonical city/district ID universe. The actual `Project` and Chroma contracts presently use `city`/`district`, so the specified `city_id` registry cannot be assumed.
- **Unverified:** Chroma operations can be made transactionally consistent with manifest publication using the current builder. The existing code only makes the manifest replacement atomic, not the preceding collection mutations.
