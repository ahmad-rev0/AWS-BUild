# Requirements Document

## Planner Dashboard

## Introduction

The Planner Dashboard is the single-page Atlas11 frontend for city planners and approvers. It submits proposals to the clash-agent API, renders validated review progress and verdicts, maps district need and funded-project context, and supports a human coordination sign-off. The frontend uses React 18, Vite, TypeScript, Tailwind CSS, Leaflet, react-leaflet, and OpenStreetMap tiles; it is designed first for a 1366×768 projector and remains a client of the authoritative FastAPI lifecycle.

## Glossary

- **Dashboard**: The React single-page planner interface defined by this specification.
- **Proposal**: A new urban-development project submitted to the API under the `Proposal` / `ProposalCreate` contract.
- **Project**: An existing funded project represented by the shared `Project` contract.
- **Review**: A server-created clash evaluation identified by the `review_id` returned in `ReviewCreated`.
- **Report**: A completed `ClashReport` containing verdicts and a memo.
- **Canonical ID**: An opaque stable ID such as `proposal_id`, `review_id`, `project_id`, `city_id`, or `district_id`, never a display name derived by the UI.
- **Seeded record**: A record whose `source` equals `seeded`; it is illustrative/cached provenance and not live or fetched data.
- **Terminal stream event**: An SSE event whose `type` is `done` or `error`.
- **Redirect**: A `REDIRECT` memo coordination target that changes only displayed map focus, never funding, allocations, or commitments.
- **Snapshot date**: A date supplied by local district/map metadata.

## Requirements

### 1. Application shell and projector layout

**User Story:** As a planning officer presenting Atlas11, I want an immediately legible desktop control room, so that I can submit, review, and coordinate a proposal without navigating between screens.

1.1 **THE Dashboard SHALL** render one React single-page dashboard with a header, persistent left panel, centre map workspace, and on-demand right drawer.

1.2 **WHEN** the viewport is 1366×768, **THE Dashboard SHALL** render a 360px left panel and a centre map workspace; with the drawer closed, the map workspace shall occupy the remaining horizontal space, and with the drawer open, the drawer shall overlay the map without removing the left panel and shall leave at least 480px of visible, operable map workspace.

1.3 **THE Dashboard SHALL** render a Planner/Approver role toggle in the header and visually indicate the active role.

1.4 **WHEN** local district/map metadata supplies a snapshot date, **THE Dashboard SHALL** display that supplied date; **IF** local district/map metadata does not supply a snapshot date, **THEN THE Dashboard SHALL** display that the snapshot date is unavailable and shall not generate or infer a date.

1.5 **THE Dashboard SHALL** use the system UI/Inter-style type stack, 14px base text, 12px dense metadata, and tabular numeric presentation for money where supported.

### 2. Shared API contracts and typed client

**User Story:** As a maintainer, I want the frontend to speak the same language as the service, so that proposal, review, and approval data retain their IDs and meaning across the system.

2.1 **THE Dashboard SHALL** define strict TypeScript mirrors of every field, closed enum, source-label subset, and nullable field in `agent/schemas.py` for `ProposalCreate`, `Proposal`, `Project`, `ReviewCreated`, `Verdict`, `Memo`, `ClashReport`, `ApprovalCreate`, `Approval`, and `SseEvent`, including `ProposalStatus`, `VerdictLabel`, `Recommendation`, and `Role` values.

2.2 **WHEN** the Dashboard submits or renders an API payload, **THE Dashboard SHALL** preserve all canonical IDs and shared snake_case field names verbatim and shall not derive a canonical ID from a display name.

2.3 **THE Dashboard SHALL** use a typed API client for `POST /proposals`, `POST /proposals/{proposal_id}/review`, `GET /reviews/{review_id}/events`, `GET /reviews/{review_id}`, and `POST /approvals`.

2.4 **WHEN** an HTTP or SSE payload has a malformed required field, an unknown closed enum value, a non-finite or out-of-range `Verdict.confidence`, a negative `SseEvent.ms`, or a non-object non-null `SseEvent.payload`, **THE Dashboard SHALL** reject the incompatible payload, show a readable compatibility error, and shall not silently coerce or render a guessed value.

2.5 **WHEN** displaying a money value from a typed API payload, **THE Dashboard SHALL** retain the received decimal value as text or an exact decimal representation without a precision-losing numeric conversion and render a compact amount format such as `US$240M` with accessible full-value text.

### 3. Proposal intake and review creation

**User Story:** As a planner, I want to submit a complete proposal and immediately see its review begin, so that coordination work starts from a consistent record.

3.1 **THE Dashboard SHALL** provide inputs for every `ProposalCreate` field: title, description, city ID, optional district ID, sector, budget USD, optional start date, optional end date, optional scenario key, and source.

3.2 **WHEN** a user submits a proposal, **THE Dashboard SHALL** locally reject only values invalid under `ProposalCreate` and `CanonicalContract`: blank title, description, city ID, or sector after trimming; a title longer than 300 characters; a description longer than 10,000 characters; a non-canonical supplied city or district ID; a budget below zero; an end date preceding a supplied start date; or a source outside `seeded` and `user`.

3.3 **WHEN** local validation succeeds and no proposal-create request is pending for the submission, **THE Dashboard SHALL** issue exactly one `POST /proposals`; **WHEN** that request returns a valid `Proposal`, **THE Dashboard SHALL** retain the returned `proposal_id`, `status`, and `source` and issue exactly one `POST /proposals/{proposal_id}/review` for that response.

3.4 **WHEN** `POST /proposals/{proposal_id}/review` returns a valid `ReviewCreated`, **THE Dashboard SHALL** retain its `review_id` and open exactly one review event stream for that stored ID.

3.5 **IF** proposal submission or review creation fails, **THEN THE Dashboard SHALL** preserve the entered form data, show the readable server message without a stack trace, and shall not create a stream or enable approval actions.

### 4. Review stream and final report

**User Story:** As a planner, I want visible review progress and a stable final report, so that I can understand when the agent is working and when a human decision is appropriate.

4.1 **WHEN** a review stream opens, **THE Dashboard SHALL** show a skeleton plus a non-blank progress status that maps schema-valid `status` events to readable text, including supplied searching, overlap-checking, and memo-drafting states.

4.2 **WHEN** the Dashboard receives a schema-valid `tool_call` SSE event with a name and a non-negative `ms` value, **THE Dashboard SHALL** append a trace row containing that tool name and duration in milliseconds.

4.3 **WHEN** the Dashboard receives a schema-valid `verdict` SSE event whose payload validates as `Verdict`, **THE Dashboard SHALL** append that verdict to the live verdict list and update its associated map relation only when a resolvable candidate location exists.

4.4 **WHEN** the Dashboard receives the first schema-valid terminal `done` event for an active stream, **THE Dashboard SHALL** close the stream, request `GET /reviews/{review_id}` using the stored `review_id`, and render a final report only after that response validates as `ClashReport`.

4.5 **IF** the Dashboard receives a terminal `error`, stream connection failure, malformed event, or final-report request failure, **THEN THE Dashboard SHALL** terminate the stream, render a readable failure state, preserve any previously received trace or verdict context as labelled partial progress, and shall not render a final memo or enable decision actions.

4.6 **WHEN** the first terminal event has been processed for an active stream, **THE Dashboard SHALL** ignore every subsequent event for that stream without changing review state; **WHEN** the dashboard unmounts, navigates, retries, or processes a terminal event, **THE Dashboard SHALL** close its active stream.

### 5. Verdict cards and provenance

**User Story:** As a planner, I want evidence-rich verdict cards, so that I can distinguish an actionable overlap from a merely similar project.

5.1 **WHEN** a `Verdict` is available, **THE Dashboard SHALL** render its exact label, project ID, confidence, matching attributes, and expandable reasoning; **WHEN** the referenced `Project` is locally resolved, **THE Dashboard SHALL** also render that Project’s name, funder, and formatted amount.

5.2 **THE Dashboard SHALL** map every valid verdict label to the required text-plus-color treatment: `DUPLICATE`/`#C0392B`, `OVERLAPPING`/`#D68910`, `COMPLEMENTARY`/`#138D75`, and `UNRELATED`/`#7F8C8D`.

5.3 **WHEN** a user selects a verdict card and the corresponding map layers exist, **THE Dashboard SHALL** visually select its candidate pin and relation line.

5.4 **WHEN** a rendered Proposal, Report, or Project has `source=seeded`, **THE Dashboard SHALL** show a `SeededBadge`; **WHEN** the rendered record has any other supported source, **THE Dashboard SHALL NOT** show a `SeededBadge` merely because the record is locally rendered.

5.5 **THE Dashboard SHALL** retain explicit source/provenance labels and shall not label a seeded record as live or fetched data.

### 6. Need map and coordination focus

**User Story:** As a planning officer, I want the proposal review in its district context, so that I can see high-need areas and coordination relationships without overstating funding.

6.1 **THE Dashboard SHALL** load district GeoJSON and associated need-score data from the local `data/geo/`-backed frontend asset path and render the polygons with a sequential 0–1 need-score choropleth.

6.2 **WHEN** district data is available, **THE Dashboard SHALL** expose the district ID, display name, need score, snapshot date, and available commitment context through a map legend, popup, or accessible equivalent.

6.3 **WHEN** a project coordinate is available from local map data, **THE Dashboard SHALL** render that funded-project pin using its funder shape; **WHEN** a proposal coordinate is available from local map data, **THE Dashboard SHALL** render a visually distinct pulsing proposal pin; **WHEN** coordinates for both related records are available, **THE Dashboard SHALL** render a candidate relation line colored and text-labelled by the corresponding Verdict label.

6.4 **WHEN** a proposal or candidate lacks a resolvable coordinate, **THE Dashboard SHALL** retain its non-map review representation and shall not fabricate a pin, location, or relation line.

6.5 **WHEN** a Report Memo has a non-null `redirect_district_id`, **THE Dashboard SHALL** show a gap/redirect callout stating that the Redirect changes coordination focus only and provide a “Show on map” action that focuses that district.

6.6 **WHEN** a redirect map action is applied, **THE Dashboard SHALL** change only selected or focused map state and shall not modify displayed funding, commitments, or need scores, or claim that the district received funding.

### 7. Memo, trace, and human approval

**User Story:** As an approver, I want the recommendation and its trace beside the map, so that I can make the only terminal coordination decision with evidence in view.

7.1 **THE Dashboard SHALL** open an on-demand right drawer containing the final Memo, the agent trace, an audit-view action, and decision controls when eligible.

7.2 **WHEN** a final Report is available, **THE Dashboard SHALL** show its recommendation and summary, any redirect callout, and the tool-call timeline in the drawer.

7.3 **WHEN** the active role is `planner`, **THE Dashboard SHALL** hide or disable approval and rejection actions and explain that an approver role is required.

7.4 **WHEN** the active role is `approver`, the current Proposal status is `REVIEWED`, and a schema-valid final Report and stored review ID exist, **THE Dashboard SHALL** enable one Approve action and one Reject action.

7.5 **WHEN** an approver chooses Reject, **THE Dashboard SHALL** require a non-empty, non-whitespace reason before sending `ApprovalCreate` with `decision: "REJECTED"`.

7.6 **WHEN** an eligible approver chooses Approve or a valid Reject, **THE Dashboard SHALL** submit exactly one schema-valid `ApprovalCreate` containing the stored review ID, a non-empty visible actor value, active `role: "approver"`, requested decision, and the applicable reason; **WHEN** the response validates as `Approval`, **THE Dashboard SHALL** render its decision and timestamp as the terminal coordination response.

7.7 **IF** an approval request fails, is denied, or returns an incompatible payload, **THEN THE Dashboard SHALL** show the readable error, retain the prior reviewed UI state, and shall not imply that a decision or funding change occurred.

7.8 **THE Dashboard SHALL** describe every accepted decision as coordination sign-off and shall not display payment, transfer, allocation, or district-funding claims.

### 8. Errors, accessibility, and resilience

**User Story:** As a demo presenter, I want the dashboard to fail safely and remain usable, so that temporary service or map issues do not turn into a misleading or inaccessible demo.

8.1 **WHEN** the API returns HTTP 503 with the exact body `{"error":"AWS credentials expired. Refresh agent/.env from Workshop Studio."}`, **THE Dashboard SHALL** show a persistent non-crashing banner stating “AWS credentials expired. Refresh agent/.env from Workshop Studio.”

8.2 **WHEN** the cached demo path reports that its cached report is unavailable, **THE Dashboard SHALL** show a readable cached-report-unavailable state and shall not fall back to or claim live review data.

8.3 **WHEN** map or GeoJSON data cannot load, **THE Dashboard SHALL** show a map-data warning while retaining proposal, review, verdict, trace, and memo content outside the map.

8.4 **THE Dashboard SHALL** make the role toggle, proposal form, verdict expansion, drawer controls, map-focus action, and decision controls keyboard operable with visible focus treatment and accessible labels.

8.5 **THE Dashboard SHALL** pair all verdict and map-relation colors with text labels or equivalent non-color identification.

8.6 **THE Dashboard SHALL** treat reasoning, memo, SSE, and API text as untrusted plain text and shall not render it as executable or unsanitized HTML.

### 9. Validation and quality gates

**User Story:** As a maintainer, I want repeatable frontend proof that the dashboard stays compatible and reliable, so that the 5-minute demo route remains safe as the service evolves.

9.1 **THE Dashboard SHALL** have Vitest unit tests for API/SSE parsing, review reducer state transitions, schema-aligned form validation, verdict rendering, seeded provenance, memo authority, and map focus behavior.

9.2 **THE Dashboard SHALL** have fast-check property tests proving terminal stream immutability, total verdict-label presentation, approval-control authority, redirect non-financiality, and seeded-badge correctness.

9.3 **THE Dashboard SHALL** provide a mocked frontend integration test for the canonical seeded path: submit proposal → stream one `OVERLAPPING` and one `COMPLEMENTARY` verdict → retrieve `CO_FINANCE` report → switch to Approver → approve → focus redirect district.

9.4 **THE Dashboard SHALL** validate the canonical demo UI path at 1366×768 with the drawer both closed and open, preserving a 360px left panel, at least 480px visible operable map workspace with the drawer open, and keyboard-operable controls.

9.5 **THE Dashboard SHALL** run TypeScript strict compilation and the narrow changed Vitest tests as its frontend quality gate.

## Non-goals

- Authentication, identity management, or frontend authorization beyond the demo Planner/Approver role toggle; the API is authoritative.
- Bedrock invocation, embedding generation, direct SQLite access, or agent taxonomy decisions in the browser.
- Financial transfers, allocation, changes to commitments, or claims that approval/redirect funded a district.
- Live scraping or externally hosted map/data services other than OpenStreetMap tiles.
- Replacing the defined React 18/Vite/TypeScript, Tailwind, Leaflet/react-leaflet stack with another UI framework.
