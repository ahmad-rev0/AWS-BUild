# Implementation Plan: Planner Dashboard

## Overview

Build the React 18 + Vite + TypeScript dashboard in layers: strict shared frontend contracts and API/SSE transport first, then review workflow state, desktop layout and panel components, the Leaflet workspace, and finally the memo/approval flow. The cached canonical scenario is the primary integration gate; map, stream, role, provenance, and redirect behavior must share the same stable IDs and contracts as the clash-agent service.

## Tasks

- [ ] 1. Establish the frontend application foundation and mirrored contracts
  - [ ] 1.1 Create the Vite React 18 TypeScript frontend structure under `frontend/`, enable TypeScript strict mode, configure Tailwind CSS, and define the API base URL configuration without adding another framework or global state library.
  - [ ] 1.2 Add `frontend/src/types/` contracts that mirror `agent/schemas.py`: canonical IDs, source labels, `Role`, `ProposalStatus`, `VerdictLabel`, `Recommendation`, `ProposalCreate`, `Proposal`, `Project`, `ReviewCreated`, `Verdict`, `Memo`, `ClashReport`, `ApprovalCreate`, `Approval`, and `SseEvent`.
  - [ ] 1.3 Add runtime boundary validators/parsers for REST payloads and SSE payloads, including finite non-negative durations/confidences and rejection of unknown enum values or malformed event payloads.
  - [ ] 1.4 Add money/date/provenance display utilities that preserve received money precision, format compact amounts such as `US$240M`, and expose source/snapshot values without inventing data.
  - [ ] 1.5 Add focused Vitest tests for contract-compatible serialization, canonical ID preservation, parser rejection paths, and money/provenance utilities.

- [ ] 2. Implement typed REST and SSE transport
  - [ ] 2.1 Add `frontend/src/api/clashApi.ts` with typed methods for `POST /proposals`, `POST /proposals/{proposal_id}/review`, `GET /reviews/{review_id}`, and `POST /approvals`, plus normalized readable `ApiError` handling.
  - [ ] 2.2 Implement a cancellable `GET /reviews/{review_id}/events` SSE client that parses each event with the shared runtime validator and stops on terminal `done` or `error`.
  - [ ] 2.3 Map the exact credential-expiry HTTP 503 body to a typed condition used by the persistent frontend banner without exposing credentials or raw response internals.
  - [ ] 2.4 Add API-client tests for request paths/bodies, successful parsing, HTTP validation/conflict/server errors, exact credential expiry handling, malformed events, terminal stream closure, and cleanup on abort.
  - [ ] 2.5 Add a required fast-check property test that generated accepted stream sequences cannot change client/reducer state after their first terminal event.

- [ ] 3. Build review workflow state and proposal intake
  - [ ] 3.1 Create `useReviewWorkflow` and a typed reducer for `idle`, `submitting`, `creating-review`, `streaming`, `complete`, and `error` states; retain proposal, review ID, event order, final report, readable error, selected role, and focused district.
  - [ ] 3.2 Implement the workflow sequence: validate/submit `ProposalCreate`, retain returned `Proposal`, create one review, open one SSE stream, append validated trace/verdict events, fetch the persisted `ClashReport` after `done`, and clean up on terminal/failure/unmount.
  - [ ] 3.3 Build `ProposalForm` with the shared proposal fields, local required/non-negative/ordered-date feedback, form-data retention after API failure, and an explicit cached scenario path where applicable.
  - [ ] 3.4 Build `RoleToggle`, `SeededBadge`, shared status/skeleton, error-banner, and snapshot-date components with accessible labels and non-blank agent progress messages.
  - [ ] 3.5 Add unit/component tests for workflow sequencing, partial-versus-final state, error preservation, form validation, stream cleanup, role selection, seeded badges, and unavailable snapshot-date fallback.
  - [ ] 3.6 Add required fast-check properties for approval action availability across generated role/status/review combinations and for seeded badge appearance iff `source === "seeded"`.

- [ ] 4. Compose the 1366×768 dashboard and verdict experience
  - [ ] 4.1 Create `PlannerDashboard` and application shell with header, 360px internally scrollable left panel, flexible centre workspace, and closed-by-default overlay right drawer; use Tailwind styling compatible with the established civic-control-room direction.
  - [ ] 4.2 Ensure 1366×768 layout keeps proposal controls, verdict list, map, and drawer controls operable; do not collapse the left panel when opening the drawer.
  - [ ] 4.3 Implement `VerdictCard` with label text/color/icon treatment, project identity/funder/amount when resolved, labelled confidence meter, matching-attribute tags, expandable reasoning, provenance badge, and map selection action.
  - [ ] 4.4 Apply the closed label palette consistently: `DUPLICATE #C0392B`, `OVERLAPPING #D68910`, `COMPLEMENTARY #138D75`, and `UNRELATED #7F8C8D`, always with non-color label text.
  - [ ] 4.5 Add component tests for all four labels, confidence/reasoning/attribute presentation, expansion, seeded provenance, card-to-map selection callback, and PlannerDashboard layout/drawer behavior.
  - [ ] 4.6 Add a required fast-check property over generated valid Verdicts proving label presentation is total and includes label text, confidence, matching attributes, and reasoning for all four labels.

- [ ] 5. Implement the Leaflet need-and-project map workspace
  - [ ] 5.1 Add `MapWorkspace` with Leaflet/react-leaflet and OpenStreetMap tiles; load district GeoJSON and need-score/snapshot data from frontend-served local `data/geo/` assets.
  - [ ] 5.2 Render a sequential district `need_score` choropleth, accessible legend/popup metadata, and a map-data-unavailable state that leaves the rest of the dashboard functional.
  - [ ] 5.3 Render funder-shaped existing-project pins, a distinct pulsing proposal pin, selected candidate highlighting, and label-colored/text-labelled proposal-to-candidate lines only for resolved coordinates.
  - [ ] 5.4 Implement `GapCallout` and map fly-to/focus by canonical `redirect_district_id`; wording and state must make clear that a redirect changes coordination focus only.
  - [ ] 5.5 Add map-focused unit tests for need-score styles, missing-coordinate omission, verdict-link correspondence, selected candidate behavior, map-data warning, and redirect focus.
  - [ ] 5.6 Add a required fast-check property test proving redirect focus leaves generated need, commitment, and funding values unchanged, and a property proving absent coordinates produce no fabricated map link.

- [ ] 6. Implement memo, agent trace, and human decision drawer
  - [ ] 6.1 Implement an on-demand right drawer containing `MemoPanel`, `AgentTrace`, audit-view action, and focus-management behavior for keyboard users.
  - [ ] 6.2 Render memo recommendation/summary, redirect callout, and a vertical trace timeline with tool names/durations and readable progress stages.
  - [ ] 6.3 Restrict interactive Approve/Reject controls to `role=approver`, a `REVIEWED` proposal, and an available final review/report; show planner users why an approver role is required.
  - [ ] 6.4 Require a non-whitespace rejection reason; submit typed `ApprovalCreate`, render returned `Approval`, and preserve reviewed state on denied/failed actions.
  - [ ] 6.5 Ensure all decision and redirect copy calls actions coordination sign-off/focus only and contains no payment, allocation, commitment increase, or funding claim.
  - [ ] 6.6 Add component tests for drawer focus/keyboard behavior, trace rendering, planner restriction, approver decision enablement, rejection validation, successful approval rendering, and denied-approval recovery.

- [ ] 7. Add canonical demo integration coverage and quality gate
  - [ ] 7.1 Create mocked frontend integration coverage for submit → review SSE → one `OVERLAPPING` and one `COMPLEMENTARY` verdict → final seeded `CO_FINANCE` report → role switch → approval → redirect district focus.
  - [ ] 7.2 Add an API-backed cached-mode smoke test that uses the live FastAPI surface when available, asserts seeded provenance and event ordering, and proves the frontend path does not require AWS/Bedrock availability.
  - [ ] 7.3 Add a 1366×768 browser/component smoke check with right drawer closed and open, including keyboard traversal, visible focus, verdict labels, seeded badge, snapshot date, map usability, and redirect copy.
  - [ ] 7.4 Run the narrow changed Vitest suite, fast-check property tests, TypeScript strict build/type check, and production Vite build. Record only factual results; do not claim that a redirect or approval funded a district.

## Task Dependency Graph

```json
{
  "waves": [
    {"id": 0, "tasks": ["1.1", "1.2"]},
    {"id": 1, "tasks": ["1.3", "1.4", "2.1"]},
    {"id": 2, "tasks": ["1.5", "2.2", "2.3", "3.1"]},
    {"id": 3, "tasks": ["2.4", "2.5", "3.2", "3.3", "3.4"]},
    {"id": 4, "tasks": ["3.5", "3.6", "4.1", "4.2"]},
    {"id": 5, "tasks": ["4.3", "4.4", "5.1", "5.2"]},
    {"id": 6, "tasks": ["4.5", "4.6", "5.3", "5.4", "6.1"]},
    {"id": 7, "tasks": ["5.5", "5.6", "6.2", "6.3", "6.4", "6.5", "6.6"]},
    {"id": 8, "tasks": ["7.1", "7.2", "7.3", "7.4"]}
  ]
}
```

## Notes

- Implement tasks in order and stop after the requested task; the cached seeded flow is the first integration gate.
- Keep `frontend/src/types/` synchronized with `agent/schemas.py`; any API contract change needs a shared schema and frontend parser/test update.
- Do not implement agent logic, geographic inference, database access, approval authorization, or funding behavior in the browser. The FastAPI service remains authoritative.
- Preserve the dashboard’s explicit source labels, data snapshot provenance, and redirect non-financial wording in all demos and tests.
