# Atlas11 spec prompts and review checklists

There are five specs, each using a **different Kiro spec workflow**, so every spec type gets used with a reason the team can explain to judges. Paste each prompt into **Chat → Spec** (or **Specs → +**), pick the stated workflow, then review each phase with the checklist **before** clicking "Move to design" or "Move to implementation". Reviewing is where your engineering judgement shows, and where you save credits: fixing a requirement costs one prompt, while fixing generated code costs ten.

| # | Spec folder | Workflow | Why this workflow (say this to judges) | Model |
|---|---|---|---|---|
| A | `data-pipeline` | **Feature, Design-First** | We already knew the architecture (fetch → normalize → embed → Chroma), so we started from design and derived requirements | Auto |
| B | `clash-agent` | **Feature, Requirements-First** + **Correctness (property-based tests)** | The core logic and safety rules had to be pinned down in EARS first; deterministic rules became testable properties | Sonnet (1.3x) for requirements and design, Auto for tasks |
| C | `planner-dashboard` | **Feature, Requirements-First** | UX flows (planner vs approver) needed user stories | Auto |
| D | `gap-finder` | **Quick Spec** | Small, well-understood computation, so one pass without approval gates was enough | Auto or a low-multiplier model |
| E | `fix-<issue>` | **Bugfix Spec** | Created from the first real defect that the eval hook or property tests catch. It records current, expected and unchanged behaviour | Auto |

**Before the first spec:** check that the steering files are loaded (type `#steering` in chat) and that the Strands Power and MCP servers show *Connected*.

## 90-minute MVP contract (applies to every spec)
The blocking path is one deterministic, seeded/cached scenario: fixed proposal ID/scenario key → review → exactly one expected `OVERLAPPING` and one expected `COMPLEMENTARY` verdict → memo → approver action → gap redirect/map state. Live Bedrock, full indexing, exhaustive evaluation, and screenshots are secondary if not already working. The pipeline, API, and frontend must share stable IDs and schemas; the minimal end-to-end smoke test is the integration gate. Every seeded result is labelled `source=seeded`; use an actual snapshot date or `TBD: needs source`, never a fabricated date.

Canonical scenario contract: `scenario_key=demo-city-transit-01` (or the implementation's fixed equivalent, documented once), proposal ID `demo-proposal-01`, city ID/name, district ID/name, sector, start date, end date, and source are required. The report must contain labels `OVERLAPPING` and `COMPLEMENTARY`, recommendation `CO_FINANCE`, and a `redirect_district_id`; approval and gap responses must work locally in `DEMO_MODE=cached` without Bedrock. City/district matching uses canonical IDs; missing districts do not match. Apply exactly 12 months of slack to both date endpoints; missing dates are conservative and cannot establish overlap.

---

## Spec A: `data-pipeline` (Feature → Design-First)

### Prompt
```
Spec: data-pipeline. Design-first.
Build the Atlas11 data pipeline as described in #steering tech.md and structure.md:
1. scripts/build_index.py: load data/processed/projects.csv (+ seeded_projects.csv if present), validate rows
   against a Pydantic Project model, embed `name + description + themes` with the provider chosen by
   EMBEDDINGS_PROVIDER (bedrock = Titan Text Embeddings V2, local = sentence-transformers all-MiniLM-L6-v2),
   and upsert into a persistent Chroma collection "projects" in data/index/ with metadata
   (city, district, sector, funder, approval_date, closing_date, amount_usd, source).
   Support --incremental (only rows whose content hash changed) because a hook calls it on every data save.
2. agent/retrieval.py: search(text, k=8, filters) -> list[Candidate(project_id, score)], with metadata filters
   for city and date window; scores normalized to [0,1], sorted descending, no duplicate IDs.
3. scripts/check_aws.py: report whether Bedrock Nova Pro and Titan embeddings are callable.
4. Seeded demo records live only in data/processed/seeded_projects.csv with source=seeded.
Use the worldbank-ingest skill if projects.csv is missing.
```

### Design review checklist
- [ ] Embedding provider is swappable by env var, and the local fallback works offline
- [ ] Incremental indexing uses a content hash (so the hook is fast)
- [ ] The Chroma path is `data/index/` and git-ignored
- [ ] There's a sequence diagram: CSV → validate → embed → upsert, plus the search path

### Requirements review: these EARS statements must be present (add them if missing)
- WHEN `build_index.py` runs, THE SYSTEM SHALL index every valid row and report rejected rows with the reason.
- WHEN `--incremental` is passed, THE SYSTEM SHALL re-embed only rows whose content hash changed.
- WHEN `search` is called with `k`, THE SYSTEM SHALL return at most `k` unique candidates sorted by descending score in [0,1].
- WHERE `EMBEDDINGS_PROVIDER=local`, THE SYSTEM SHALL build and search the index without network access.

### Tasks review
- Keep optional tasks optional, **except** the test for `search` ordering and uniqueness. Make that one required.

---

## Spec B: `clash-agent` (Feature → Requirements-First + Correctness)

This is the heart of Innovation and Technical. Review it most carefully.

### Prompt
```
Spec: clash-agent. Requirements-first.
Build the Atlas11 clash review agent following #steering agent-guardrails.md and sdg11-domain.md, and
#file:agent/AGENTS.md. Use the Strands Agents SDK (use the Strands power for correct APIs) with Bedrock Nova Pro.
- FastAPI app (agent/app.py): POST /proposals, POST /proposals/{id}/review (returns review_id),
  GET /reviews/{id}/events (Server-Sent Events streaming agent progress + tool calls),
  GET /reviews/{id} (final ClashReport), POST /approvals, GET /audit.
  Review completion moves SUBMITTED to REVIEWED; only an approver may approve/reject, rejection requires a reason, and approval never moves money.
  SSE events use `{type, name?, ms?, payload?}` and are ordered status → tool_call(s) → verdict(s) → done, or error instead of done. Audit rows contain event type, relevant IDs, actor/role, UTC timestamp, and payload summary.
- Tools in agent/tools/: search_similar_projects, get_project, check_overlap (deterministic geo/time/sector
  facts, no LLM), district_need, draft_memo.
- Post-processing validator enforcing the taxonomy rules (different city => never DUPLICATE/OVERLAPPING;
  DUPLICATE requires >= 2 matching attributes else downgrade to OVERLAPPING and log).
- Approval state machine: SUBMITTED -> REVIEWED -> APPROVED | REJECTED; only role=approver may transition
  to APPROVED/REJECTED.
- agent/eval.py: golden-pair evaluation (--quick = first 6 pairs) appending to .kiro/evidence/eval-history.csv.
- DEMO_MODE=cached serves data/demo_cache responses; expired AWS credentials -> HTTP 503 with refresh message.
```

### Requirements review: required EARS statements
- WHEN a planner submits a review request, THE SYSTEM SHALL filter by city, optional district, sector, and implementation date window, retrieve at most 8 candidates, and send at most 5 to the model after deterministic filtering.
- WHEN a candidate's city differs from the proposal's city, THE SYSTEM SHALL NOT label it DUPLICATE or OVERLAPPING.
- WHEN the implementation periods don't overlap within 12 months, THE SYSTEM SHALL NOT label the pair DUPLICATE or OVERLAPPING.
- `DUPLICATE` requires at least two matching attributes; concrete outputs and the taxonomy decision rules still govern the final label. If a model emits `DUPLICATE` with fewer than two, downgrade it to `OVERLAPPING` and record the downgrade in the audit log.
- THE SYSTEM SHALL NOT change a proposal's status except through the defined state machine: review completion moves `SUBMITTED` to `REVIEWED`, then only an approver may move it to `APPROVED` or `REJECTED`; rejection requires a reason and no transition moves money.
- WHEN the model output fails schema validation, THE SYSTEM SHALL retry once with the validation error and, if it fails again, return HTTP 502 with a readable message.
- WHILE `DEMO_MODE=cached`, THE SYSTEM SHALL resolve the canonical scenario by its fixed key/proposal ID without Bedrock, and approval/gap responses SHALL be deterministic or locally backed.
- THE SYSTEM SHALL use the shared IDs/schemas across pipeline, API, and frontend; the minimal end-to-end smoke test SHALL be the integration gate.
- IF Bedrock rejects the credentials as expired, THEN THE SYSTEM SHALL return HTTP 503 with the message "AWS credentials expired. Refresh agent/.env from Workshop Studio."
- WHILE `DEMO_MODE=cached`, THE SYSTEM SHALL serve cached reports for scripted proposals without calling Bedrock.
- WHEN a review runs, THE SYSTEM SHALL emit a progress event for every tool call, with name and duration.
- THE SYSTEM SHALL record every verdict, tool call and approval in the audit log with a timestamp.

### Correctness: properties Kiro should extract (check they appear; add any that are missing)
The LLM itself isn't property-testable, but **everything around it is**, and that's the point to make to judges.
1. `check_overlap` is symmetric: overlap(a,b) == overlap(b,a) for geography and dates.
2. For any generated proposal and candidate in different cities, the validator's final label ∉ {DUPLICATE, OVERLAPPING}.
3. For any verdict, after validation, the label is DUPLICATE ⇒ `len(matching_attributes) ≥ 2`.
4. Confidence is always in [0,1], and the label is always one of the 4 enum values.
5. Approval state machine: for any sequence of actions by random roles, a proposal reaches APPROVED or REJECTED only if the last transition was by an approver, and never skips REVIEWED.
6. `search` returns ≤ k unique IDs sorted by score (shared with Spec A).

When running the PBT tasks, **make them required, not optional.** If a property fails, Kiro shrinks the failing input to the smallest case. Screenshot that: it's your strongest Technical slide.

### Design review checklist
- [ ] Tools return facts; the model only reasons (no date maths in the prompt)
- [ ] The system prompt is in `agent/prompts/clash_system.md` (watched by the eval hook)
- [ ] SSE events carry `{type, name?, ms?, payload?}`; `status` precedes `tool_call` events, then `verdict`, then `done` (or `error` instead of `done`)
- [ ] A cached-mode code path exists at the API layer, not inside the agent, keyed by the canonical scenario key/proposal ID and covering review, approval, and gap responses

### Tasks review
- Run tasks **one at a time** with ⚡ *Start task* (the lab recommends this), in Supervised mode for the first three tasks, then Autopilot once the tests pass.
- After the eval task is done, label at least 12 golden pairs (clash-eval skill, data-steward agent), then iterate on the prompt. The hook re-runs the eval on every save.

---

## Spec C: `planner-dashboard` (Feature → Requirements-First)

### Prompt
```
Spec: planner-dashboard. Requirements-first.
Build the Atlas11 React + Vite + TS frontend per #steering frontend-design.md, consuming the API from
#spec clash-agent. Single page: proposal form (left), Leaflet map with district need choropleth and
project pins (centre), memo + agent trace + approve/reject drawer (right). Role toggle Planner/Approver.
Stream review progress from GET /reviews/{id}/events. Show "Seeded for demo" badges and the data snapshot
date. Must be fully usable at 1366x768. Types in frontend/src/types/api.ts mirror agent/schemas.py.
```

### Required user stories and EARS
- As a planner, I submit a proposal and watch the agent's progress live.
  - WHEN a review is running, THE SYSTEM SHALL display each progress event within 1 second of receipt.
- As an approver, I approve or reject a recommendation with a reason.
  - WHILE the role is Planner, THE SYSTEM SHALL hide the approve and reject controls.
- As a judge watching, I see why the agent decided.
  - WHEN a verdict is selected, THE SYSTEM SHALL highlight the candidate on the map and show its matching attributes.
- IF the API returns 503 (expired credentials), THEN THE SYSTEM SHALL show a non-blocking banner with the refresh instruction.

### Afterwards
- Ask Kiro to use the **Playwright MCP** to open the app at 1366×768, run the demo flow and save screenshots to `docs/screenshots/`.

---

## Spec D: `gap-finder` (Quick Spec)

### Prompt
```
Quick spec: gap-finder.
agent/gaps.py + scripts/build_need_scores.py: read data/geo/districts.geojson and data/geo/district_indicators.csv
(columns: district_id, district_name, population, population_density, informal_settlement_share, flood_exposure,
transport_access_gap, indicator_quality), min-max normalize each indicator, combine with weights from
data/geo/need_weights.json into need_score in [0,1], join funded commitments per district from the project index,
compute funding_per_capita, flag gaps (need_score >= 0.6 and funding_per_capita in bottom quartile), write
data/geo/need_scores.csv, and expose GET /gaps. Add Hypothesis properties: need_score in [0,1]; increasing any
positively-weighted indicator never decreases need_score.
```

---

## Spec E: Bugfix spec (when the first real defect appears)

Trigger it from a real failure: an eval regression, a property-test counterexample or a demo-flow bug. **Don't invent a bug for show.** Example prompt:
```
Bugfix spec: <short-name>.
Current behaviour: <what happens, with the failing command / counterexample>.
Expected behaviour: <what should happen, referencing the EARS requirement ID>.
Unchanged behaviour: all other golden pairs keep their labels; existing tests stay green.
```
Kiro records this in `bugfix.md`. In the pitch: "the property test found X, the bugfix spec fixed it without regressions."

---

## Context providers: what to attach to which prompt
| Situation | Attach |
|---|---|
| Starting or continuing spec tasks | `#spec <name>` |
| After switching Kiro accounts | `#file:.kiro/evidence/HANDOFF.md` + `#spec <name>` |
| A test or command failed | `#terminal` (or `#problems` for type errors) |
| Reviewing what changed before a commit | `#git diff` |
| Asking about Strands or Bedrock APIs | `#mcp` (aws-docs) or rely on the Strands Power |
| Cross-cutting question ("where do we compute overlap?") | `#codebase` |
| External reference page | `#url <link>` |
