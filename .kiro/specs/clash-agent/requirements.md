# Requirements Document

## Atlas11 Clash Review Agent

## Introduction

This specification defines the Atlas11 clash review agent. The agent compares a submitted urban-development proposal with existing funded projects, returns a schema-validated coordination report, preserves human approval authority, and supports a deterministic offline demo. The scope uses the established FastAPI, SQLite, Strands, Bedrock, Pydantic, retrieval, and local-cache boundaries; approval is coordination sign-off only and never moves or allocates funds.

## Glossary

- **Atlas11 Service**: The API, lifecycle, validation, persistence, and event-streaming boundary described by this specification.
- **Proposal**: A new urban-development project submitted for coordination review.
- **Project**: An existing funded project represented by the shared `Project` contract.
- **Review**: One evaluation of a Proposal with one stable `review_id` and, on success, one final `ClashReport`.
- **Verdict**: The validated classification of one Proposal/Project pair: `DUPLICATE`, `OVERLAPPING`, `COMPLEMENTARY`, or `UNRELATED`.
- **Memo**: The structured coordination recommendation: `MERGE`, `CO_FINANCE`, `PROCEED`, or `REDIRECT`.
- **Canonical ID**: A stable machine identifier for a Proposal, Project, Review, district, city, or approval. A display name is not a Canonical ID.
- **Cached Demo**: The locally served seeded scenario enabled by `DEMO_MODE=cached`.
- **Approver**: An actor whose request has `role=approver`.
- **Terminal SSE event**: An `error` or `done` event after which the review stream emits no additional events.
- **Readable error**: A response whose JSON payload contains a non-empty `error` or `detail` string and contains no stack trace, credential value, raw session token, or secret.
- **Matching attribute**: A distinct, concrete evidence item about location, named output, beneficiary group, taxonomy, or implementation period; generic sector wording and text similarity alone are not Matching Attributes.

## Requirements

### 1. Shared contracts and proposal intake

**User Story:** As a planner, I want Atlas11 to validate and retain a proposal consistently, so that review, persistence, and frontend views refer to the same coordination record.

1.1 **WHEN** a client sends `POST /proposals`, **THE Atlas11 Service SHALL** validate the request with a Pydantic model containing a title of 1–300 characters, a description of 1–10,000 characters, a non-empty canonical `city_id`, an optional canonical `district_id`, a non-empty sector, a non-negative budget, optional `start_date` and `end_date`, an optional scenario key, and `source` equal to `user` or `seeded`.

1.2 **WHEN** a valid proposal request is accepted, **THE Atlas11 Service SHALL** generate one stable `proposal_id`, persist a Proposal with status `SUBMITTED` and a UTC `submitted_at` timestamp, append a proposal-intake audit row in the same transaction, and return the persisted validated Proposal with HTTP 201.

1.3 **IF** a proposal request includes both implementation dates and `end_date` precedes `start_date`, **THEN THE Atlas11 Service SHALL** return a readable HTTP 422 validation response, create no Proposal or audit row for the rejected intake, and leave existing records unchanged.

1.4 **THE Atlas11 Service SHALL** preserve the same Canonical IDs and compatible Pydantic/TypeScript payload field names for Proposals, Projects, Reviews, districts, and approvals across pipeline output, API payloads, cached records, SQLite rows, and the frontend integration boundary.

1.5 **WHEN** a Proposal or Cached Demo record has `source=seeded`, **THE Atlas11 Service SHALL** persist and return `source=seeded` unchanged and label no seeded record as fetched or live data.

### 2. Review creation and candidate preparation

**User Story:** As a planner, I want a review request to have a bounded, traceable candidate set, so that the agent considers relevant funded projects without changing an ineligible proposal.

2.1 **WHEN** a planner sends `POST /proposals/{proposal_id}/review` for an existing Proposal in `SUBMITTED`, **THE Atlas11 Service SHALL** create exactly one stable `review_id`, append a review-created audit row, and return HTTP 202 with that `review_id` before or while review processing starts.

2.2 **WHEN** a live review begins, **THE Atlas11 Service SHALL** retrieve no more than eight candidate Projects, apply canonical city ID, optional known district ID, sector, and known implementation-window filters deterministically, remove duplicate Project IDs without changing retained retrieval order, and provide no more than five retained candidates to the model.

2.3 **WHEN** a Proposal has no district ID or its district ID is unknown, **THE Atlas11 Service SHALL** set district-match evidence to false and exclude the absent or unknown district from positive district matching.

2.4 **WHEN** the live-review orchestration invokes a tool, **THE Atlas11 Service SHALL** measure a non-negative elapsed duration in milliseconds, append a sanitized tool-call audit row containing the tool name and duration, and emit one corresponding `tool_call` SSE event.

2.5 **IF** `proposal_id` does not identify a stored Proposal, **THEN THE Atlas11 Service SHALL** return HTTP 404 with a readable error, create no Review, append no review-created audit row, and leave all Proposal statuses unchanged.

2.6 **IF** a Review is requested for a Proposal whose status is not `SUBMITTED`, **THEN THE Atlas11 Service SHALL** return HTTP 409 with a readable error, create no second Review, append no review-created audit row, and preserve the Proposal status.

### 3. Strands agent and deterministic tools

**User Story:** As a coordination officer, I want the model to reason from bounded deterministic evidence, so that classifications are reproducible and auditable.

3.1 **WHEN** the Atlas11 Service constructs the live-review agent, **THE Atlas11 Service SHALL** configure one Strands `Agent` for the account-exposed Amazon Bedrock Nova Pro model and load all system-prompt text exclusively from `agent/prompts/clash_system.md`.

3.2 **THE Atlas11 Service SHALL** calculate canonical geography, implementation-period, sector, beneficiary/output, and district-need facts in deterministic Python tools and provide those facts to the model without asking the model to calculate or invent them.

3.3 **THE Atlas11 Service SHALL** provide exactly one model-facing tool per file in `agent/tools/` for `search_similar_projects.py`, `get_project.py`, `check_overlap.py`, `district_need.py`, and `draft_memo.py`; each tool SHALL have a model-facing docstring and Pydantic input and output models.

3.4 **WHEN** `search_similar_projects(proposal_text, k)` is called, **THE Atlas11 Service SHALL** return at most `k` unique stable Project IDs with normalized similarity scores for non-empty `proposal_text` and `1 <= k <= 8`, or return a typed validation failure without calling retrieval for an empty `proposal_text` or an out-of-range `k`.

3.5 **WHEN** `get_project(project_id)` is called, **THE Atlas11 Service SHALL** return the canonical Project record and provenance for a non-empty stable Project ID present in the local project source, or a typed validation or not-found failure without fabricating a Project.

3.6 **WHEN** `check_overlap(proposal, project_id)` receives validated inputs, **THE Atlas11 Service SHALL** return the referenced Project ID, canonical city and district equality, district-known status, date-evidence availability, inclusive period-overlap evidence using exactly 12 calendar months of slack at each known endpoint, sector evidence, beneficiary/output evidence, and distinct Matching Attributes.

3.7 **WHEN** `district_need(district_id)` is called, **THE Atlas11 Service SHALL** return locally available need-score and current-funding facts for a known Canonical ID, or a typed not-found failure without inferring a need score or funding result for an unknown district.

3.8 **WHEN** `draft_memo(verdicts)` receives validated Verdicts, **THE Atlas11 Service SHALL** return a schema-valid Memo consistent with those Verdicts and, when the Memo uses `REDIRECT`, set only a coordination target and map focus while preserving all funded-commitment values.

### 4. Clash taxonomy and post-processing validation

**User Story:** As a planning officer, I want each verdict constrained by geography, time, and concrete evidence, so that similarity alone cannot create a severe coordination recommendation.

4.1 **WHEN** a candidate Project has a canonical city ID different from the Proposal canonical city ID, **THE Atlas11 Service SHALL** validate the final label as `COMPLEMENTARY` or `UNRELATED`, never `DUPLICATE` or `OVERLAPPING`.

4.2 **WHEN** both Proposal and Project have complete implementation intervals and the intervals intersect after extending each start by exactly 12 calendar months earlier and each end by exactly 12 calendar months later, **THE Atlas11 Service SHALL** record time evidence as overlapping, including intersections at a boundary date.

4.3 **WHEN** either the Proposal or Project lacks an implementation start or end date, **THE Atlas11 Service SHALL** record `dates_known=false` and `periods_overlap_with_slack=false` and prevent time evidence alone from supporting `DUPLICATE` or `OVERLAPPING`.

4.4 **WHEN** complete known implementation intervals do not intersect under the exactly-12-calendar-month slack rule, **THE Atlas11 Service SHALL** prevent time evidence from supporting `DUPLICATE` or `OVERLAPPING`.

4.5 **WHEN** canonical city IDs match and known canonical district IDs differ, **THE Atlas11 Service SHALL** validate the pair no more severely than `OVERLAPPING` and allow `OVERLAPPING` only when deterministic evidence identifies shared beneficiaries.

4.6 **WHEN** the Atlas11 Service validates `DUPLICATE`, **THE Atlas11 Service SHALL** require concrete output and taxonomy evidence in addition to at least two distinct Matching Attributes and SHALL not treat text similarity or generic sector wording as sufficient duplicate evidence.

4.7 **IF** model output labels a pair `DUPLICATE` with fewer than two distinct Matching Attributes after deterministic evidence is merged, **THEN THE Atlas11 Service SHALL** change only that label to `OVERLAPPING`, retain the cited Project ID, and append one taxonomy-downgrade audit row before the report is persisted.

4.8 **WHEN** validated evidence is insufficient for a requested severity, **THE Atlas11 Service SHALL** select the least severe supported taxonomy label and retain a finite confidence score in the inclusive range `[0,1]`.

4.9 **WHEN** the Atlas11 Service returns a Verdict externally, **THE Atlas11 Service SHALL** return exactly one label from `DUPLICATE`, `OVERLAPPING`, `COMPLEMENTARY`, or `UNRELATED` and a finite confidence score in the inclusive range `[0,1]`.

### 5. Structured agent output and final review state

**User Story:** As a planner, I want a review to become visible only after its report has been validated and stored, so that an incomplete agent response cannot change coordination state.

5.1 **WHEN** the live agent completes an invocation, **THE Atlas11 Service SHALL** parse the output into the Pydantic `ClashReport` contract containing the requested `proposal_id`, validated Verdicts, a Memo, `model_id`, non-negative `latency_ms`, and source before exposing a final report through the API.

5.2 **IF** the first live-agent output fails Pydantic `ClashReport` validation, **THEN THE Atlas11 Service SHALL** invoke the model exactly once more with the validation feedback and shall make no Proposal status change before the retry result validates.

5.3 **IF** the retry output fails Pydantic `ClashReport` validation, **THEN THE Atlas11 Service SHALL** append a sanitized report-validation-failure audit row, return a readable HTTP 502 error or terminal SSE `error`, persist no unvalidated report, preserve the Proposal in `SUBMITTED`, and emit no `done` event.

5.4 **WHEN** a report passes Pydantic parsing and taxonomy post-processing, **THE Atlas11 Service SHALL** persist the validated report, change the Proposal status from `SUBMITTED` to `REVIEWED`, and append report-completed and Verdict audit rows in one database transaction.

5.5 **IF** retrieval, a tool, Bedrock, report validation, or persistence fails before review completion, **THEN THE Atlas11 Service SHALL** preserve the Proposal in `SUBMITTED`, avoid persisting a final report, append the applicable sanitized failure audit row when persistence remains available, and return or stream a Readable Error without a `done` event.

### 6. Server-Sent Events and review access

**User Story:** As a planner, I want a review stream with an unambiguous completion state, so that the interface can render progress without interpreting partial agent output as a final decision.

6.1 **WHEN** a client calls `GET /reviews/{review_id}/events` for an existing Review, **THE Atlas11 Service SHALL** emit Server-Sent Events whose JSON payload validates as `SseEvent` with `type`, optional `name`, optional non-negative `ms`, and optional object `payload`.

6.2 **WHEN** a Review succeeds, **THE Atlas11 Service SHALL** emit one or more initial `status` events, then zero or more `tool_call` events, then one `verdict` event for each persisted validated Verdict, and exactly one terminal `done` event containing the `review_id` and final-report reference; no event SHALL follow that `done` event.

6.3 **WHEN** a Review fails after event streaming begins, **THE Atlas11 Service SHALL** emit exactly one terminal `error` event with a Readable Error payload, emit no `done` event, and emit no event after that `error` event.

6.4 **WHEN** the Atlas11 Service emits a `tool_call` SSE event, **THE Atlas11 Service SHALL** include the invoked tool `name` and a non-negative elapsed `ms` value that matches the corresponding audit row.

6.5 **WHEN** a client calls `GET /reviews/{review_id}` after successful completion, **THE Atlas11 Service SHALL** return only the persisted validated `ClashReport`; **WHILE** that Review has not completed, **THE Atlas11 Service SHALL** return a readable pending or not-found response and return no partial unvalidated agent output.

### 7. Approval state machine and human authority

**User Story:** As an approver, I want to make the only terminal coordination decision after review, so that a planner or agent cannot approve, reject, or imply funding.

7.1 **THE Atlas11 Service SHALL** permit Proposal status transitions only in the order `SUBMITTED -> REVIEWED -> APPROVED` or `SUBMITTED -> REVIEWED -> REJECTED`.

7.2 **WHEN** the Atlas11 Service receives an approval request for a `REVIEWED` Proposal from an Approver, **THE Atlas11 Service SHALL** perform exactly one requested terminal transition, persist one Approval with stable `approval_id`, Review ID, Proposal ID, actor, role, decision, UTC timestamp, and optional reason, and append the success audit row in the same transaction.

7.3 **IF** an approval request role is not `approver`, **THEN THE Atlas11 Service SHALL** return HTTP 403 with a Readable Error, append a denied-approval audit row, create no Approval, and preserve the Proposal status.

7.4 **IF** an approval request references a Proposal whose status is not `REVIEWED`, **THEN THE Atlas11 Service SHALL** return HTTP 409 with a Readable Error, append a denied-transition audit row, create no Approval, and preserve the Proposal status.

7.5 **IF** an approval request selects `REJECTED` and the reason is missing or whitespace-only, **THEN THE Atlas11 Service SHALL** return HTTP 422 with a Readable Error, append a rejected-request audit row, create no Approval, and preserve the Proposal status.

7.6 **WHEN** the Atlas11 Service accepts or denies an approval or rejection request, **THE Atlas11 Service SHALL** append an audit row with applicable Proposal, Review, Approval, actor, and role values, UTC timestamp, event type, and a short sanitized payload summary.

7.7 **THE Atlas11 Service SHALL** perform no payment, fund transfer, funding allocation, commitment increase, or claim that a Proposal approval or Memo redirect funded a district during review or approval processing.

### 8. Audit trail

**User Story:** As a senior coordination officer, I want a complete sanitized audit trail, so that each final recommendation and human decision can be reviewed without exposing credentials.

8.1 **WHEN** Atlas11 receives proposal intake, creates a Review, invokes a tool, validates a Verdict, downgrades taxonomy, completes or fails a report, receives an approval/rejection request, or accepts or denies an approval/rejection, **THE Atlas11 Service SHALL** append one audit record for that event.

8.2 **WHEN** the Atlas11 Service appends an audit record, **THE Atlas11 Service SHALL** store event type, UTC timestamp, a non-empty sanitized payload summary, and each applicable Proposal, Review, Project, Approval, actor, and role ID or value.

8.3 **WHEN** a client calls `GET /audit` with optional `proposal_id` and/or `review_id` filters, **THE Atlas11 Service SHALL** return only audit rows matching every supplied filter and exclude credential values, raw session tokens, and other secrets from every returned field.

8.4 **WHEN** the Atlas11 Service returns successful review completion or approval/rejection completion, **THE Atlas11 Service SHALL** commit the associated durable status change, final report or Approval row, and all required audit rows atomically and, if that transaction cannot commit, return a Readable Error and preserve the pre-transition durable state.

### 9. Cached demo and offline resilience

**User Story:** As a demo presenter, I want the canonical review path to work without external services, so that the SDG 11 coordination story remains deterministic when credentials or indexing are unavailable.

9.1 **WHILE** `DEMO_MODE=cached`, **THE Atlas11 Service SHALL** resolve only the canonical scenario key `demo-city-transit-01` or canonical Proposal ID `demo-proposal-01` from `data/demo_cache/` and shall invoke neither Bedrock nor live retrieval for that canonical review.

9.2 **WHEN** a canonical Cached Demo review is requested, **THE Atlas11 Service SHALL** return and persist a schema-validated `source=seeded` report containing exactly one `OVERLAPPING` Verdict, exactly one `COMPLEMENTARY` Verdict, a `CO_FINANCE` Memo recommendation, and a canonical redirect district ID.

9.3 **WHILE** `DEMO_MODE=cached`, **THE Atlas11 Service SHALL** emit deterministic schema-valid review SSE events with the terminal semantics in Requirement 6, persist locally backed approval actions, and expose locally backed redirect and gap-map state without a Bedrock, index, AWS-credential, or network dependency other than optional map tiles.

9.4 **IF** the required cached report is missing, unreadable, or invalid under `ClashReport` validation, **THEN THE Atlas11 Service SHALL** return or stream a Readable Error identifying the cached report as unavailable, preserve existing Proposal and Review records, and shall not fall back to Bedrock or live retrieval.

9.5 **WHEN** the canonical Cached Demo is repeated from the same stored `SUBMITTED` Proposal state, **THE Atlas11 Service SHALL** produce the same report fields, Verdict labels, Memo recommendation, redirect district ID, and event-type sequence for each execution.

### 10. Credentials, timeouts, and evaluation

**User Story:** As an operator, I want bounded live failures and reproducible evaluation, so that expired workshop credentials cannot expose secrets or break the cached demo path.

10.1 **WHEN** the Atlas11 Service invokes Bedrock for a live review, **THE Atlas11 Service SHALL** apply a 20-second timeout and return or stream a Readable Error rather than a stack trace when the timeout expires.

10.2 **WHEN** a live review begins or the Atlas11 Service retries after a credential error, **THE Atlas11 Service SHALL** reload environment values from `agent/.env` and recreate the boto3 session before the next live Bedrock invocation.

10.3 **IF** Bedrock returns `ExpiredTokenException`, `UnrecognizedClientException`, or `ExpiredToken`, **THEN THE Atlas11 Service SHALL** return HTTP 503 with exactly `{ "error": "AWS credentials expired. Refresh agent/.env from Workshop Studio." }`, append a sanitized credential-failure audit row, and preserve the Proposal status.

10.4 **THE Atlas11 Service SHALL** exclude credential values, raw session tokens, and secrets from tracked files, API responses, audit rows, exception bodies, and logs.

10.5 **WHEN** `python -m agent.eval --quick` runs against `data/eval/golden_pairs.jsonl`, **THE Atlas11 Service SHALL** evaluate the first six valid labelled pairs in file order, report per-run evaluation outcomes, and append one timestamped result row to `.kiro/evidence/eval-history.csv`.

10.6 **WHEN** full evaluation runs, **THE Atlas11 Service SHALL** evaluate every valid labelled pair in `data/eval/golden_pairs.jsonl`; the maintained valid set SHALL contain at least 12 human-labelled pairs spanning all four Verdict labels, different-city cases, inclusive 12-month date-boundary cases, same-city/different-district cases, missing-date cases, and the canonical Cached Demo scenario.

10.7 **WHEN** a system-prompt file under `agent/prompts/` changes, **THE Atlas11 Service SHALL** run the configured prompt regression check, record the evaluation result, and require explicit human review before accepting a change that lowers golden-pair accuracy.

### 11. Correctness property requirements

**User Story:** As a maintainer, I want universal invariants for coordination logic, so that bounded deterministic rules are checked beyond a small set of examples.

11.1 **WHEN** deterministic geography and date-overlap facts are calculated for two fully specified Proposal/Project representations, **THE Atlas11 Service SHALL** produce the same equality and inclusive-slack-overlap facts after exchanging the operands.

11.2 **WHEN** a generated Proposal/Project pair has different canonical city IDs, **THE Atlas11 Service SHALL** validate the final Verdict as neither `DUPLICATE` nor `OVERLAPPING`.

11.3 **WHEN** a generated Verdict is accepted with label `DUPLICATE`, **THE Atlas11 Service SHALL** retain at least two distinct Matching Attributes.

11.4 **WHEN** a generated Verdict is accepted for external return, **THE Atlas11 Service SHALL** retain one closed taxonomy label and a finite confidence in `[0,1]`.

11.5 **WHEN** a generated sequence of lifecycle actions and actor roles reaches `APPROVED` or `REJECTED`, **THE Atlas11 Service SHALL** have reached `REVIEWED` first and applied a final Approver transition.

11.6 **WHEN** a generated SSE event sequence is accepted, **THE Atlas11 Service SHALL** enforce an initial `status`, all `tool_call` events before all `verdict` events, and exactly one terminal `done` for a successful sequence, or exactly one terminal `error` and no `done` for a failed sequence.

11.7 **WHEN** a generated live-review candidate collection is selected, **THE Atlas11 Service SHALL** retain at most eight unique retrieval candidates and at most five deterministic model candidates while preserving retained retrieval order.

11.8 **WHEN** a generated canonical Cached Demo review is executed, **THE Atlas11 Service SHALL** invoke neither Bedrock nor live retrieval and return a `source=seeded` report that validates as `ClashReport`.

## Non-goals

- User accounts or authentication beyond the supplied planner/approver role value.
- Payment, financial transfer, funding allocation, or changes to funded commitments.
- Live data scraping during the demo.
- Any claim that a redirect or approval funded, delivered, or measured a district outcome.
