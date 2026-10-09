---
inclusion: fileMatch
fileMatchPattern: ["agent/**"]
---
# Agent design guardrails (Strands + Bedrock Nova Pro)

## Human in the loop: non-negotiable
- Review completion moves `SUBMITTED` to `REVIEWED`; the agent still never approves, changes funding, or allocates funds.
- Only `role=approver` may transition `REVIEWED` to `APPROVED` or `REJECTED`; rejection requires a reason. Approval is coordination sign-off only and does not fund a district or move money.
- Every recommendation shows the reasoning, the cited evidence (project IDs + matching attributes) and a confidence score.

## Deterministic demo and transport contract
- With `DEMO_MODE=cached`, the fixed scripted scenario key/proposal ID serves its cached report without Bedrock. Approval and gap responses are deterministic/local; cache records are labelled `source=seeded`.
- Review SSE events use `{type, name?, ms?, payload?}`. `status` events describe progress, `tool_call` events name the tool and duration, `verdict` events carry one validated verdict, `done` carries the final review ID/report reference, and `error` carries a readable error. Order is status → tool_call(s) → verdict(s) → done, or error instead of done.
- Audit rows minimally contain `event_type`, proposal/review/project/approval IDs when applicable, actor and role when applicable, UTC timestamp, and a short payload summary.

## Agent shape
- One Strands `Agent` with a system prompt loaded from `agent/prompts/clash_system.md`.
- Tools (one file each in `agent/tools/`):
  - `search_similar_projects(proposal_text, k)`: vector search; returns IDs and scores only
  - `get_project(project_id)`: full record of one project
  - `check_overlap(proposal, project_id)`: deterministic geography, time and sector overlap facts (no LLM)
  - `district_need(district_id)`: need score and current funding for a district
  - `draft_memo(verdicts)`: produces the coordination memo structure
- Deterministic facts (distance, date overlap, same district) are computed **in Python tools**, never guessed by the model. The model reasons over the facts.

## Output contract
The final agent output must parse into `ClashReport` (Pydantic):
```
ClashReport { proposal_id, candidates: [Verdict], memo: Memo, model_id, latency_ms }
Verdict { project_id, label: DUPLICATE|OVERLAPPING|COMPLEMENTARY|UNRELATED,
          confidence: float[0,1], matching_attributes: [str], reasoning: str }
Memo { recommendation: MERGE|CO_FINANCE|PROCEED|REDIRECT, summary: str, redirect_district_id?: str }
```
- If parsing fails, retry once with the validation error appended; then return HTTP 502 with a readable message.
- A `DUPLICATE` with fewer than 2 `matching_attributes` is invalid. Downgrade it to `OVERLAPPING` and log it.

## Cost and latency
- Retrieve at most `k=8` candidates after filtering by city, optional district, sector and implementation date window; send at most 5 to the model after deterministic filtering.
- Keep the system prompt under about 1,200 tokens. Put the taxonomy in the prompt, not long examples.
- Log tool calls and timings to the audit table. The UI shows them as a "How the agent decided" panel, which is a strong demo moment.

## Prompt changes
- Prompts live in `agent/prompts/`. Saving one triggers the eval hook (`python -m agent.eval --quick`).
- Don't merge a prompt change that lowers golden-pair accuracy.
