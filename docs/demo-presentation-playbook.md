# Atlas11 demo presentation playbook

**Format:** 5:00 presentation + 2:00 Q&A  
**Team:** 4 presenters — two Business students and two Computer Science students  
**Product:** Atlas11 — a decision-support prototype for urban development coordination under SDG 11

> **Core promise:** Atlas11 helps planning and development-finance teams see where urban development projects are concentrated, where local need is high but visible funding is low, and which new proposals may duplicate, overlap with, or complement existing projects. It recommends coordination; a human approver signs off. It does **not** move money, allocate funding, or claim that a redirect funds a district.

## 1. Presentation strategy

### The single story
A planner receives a new urban proposal. Atlas11 compares it to funded projects, separates a meaningful overlap from a look-alike that is actually complementary, drafts a coordination memo, requires a human approval decision, and focuses the map on a high-need district. The final point is not “AI replaces planning.” It is: **AI makes coordination evidence visible, while people retain authority.**

### What judges should remember

1. **Innovation:** Atlas11 reasons over geography, implementation period, concrete outputs, and beneficiaries — not just semantic similarity.
2. **Technical implementation:** the agent is constrained by deterministic tools, Pydantic schemas, typed contracts, evaluation, property-based correctness rules, auditability, cached-mode resilience, and a human approval state machine.
3. **SDG impact:** Atlas11 makes an operational contribution to SDG 11 coordination, with 11.c as the primary policy framing and district-level need/funding visibility as the practical mechanism.
4. **Kiro implementation:** Kiro was used as an engineering system, not merely as autocomplete: steering, Specs, EARS requirements, property tests, hooks, skills, scoped agents, MCP configuration, and evidence artifacts deliberately shape the build and demo.

### Claim discipline — use these exact guardrails

- Say **“prototype,” “decision support,” “coordination recommendation,”** and **“visible funding gap”** — not “funding allocation,” “savings achieved,” or “money redirected.”
- Say **“computed from our local project dataset”** for metrics below. Do not generalize that dataset to all development finance.
- Say **“illustrative”** whenever the demo district need indicator is shown. The current local output identifies `Atlas11 Demo District High` as `indicator_quality=illustrative`.
- Say **“evaluation dataset,”** not “real-world accuracy,” for the golden-pair score.
- Do not say multiple funders are represented in the current snapshot: the local `projects.csv` impact script reports **323 projects, all World Bank**. “Multi-funder” is the product’s intended scale, not a demonstrated property of the present dataset.

## 2. Five-minute running order and presenter ownership

| Time | Slide / action | Lead | Target criterion |
|---|---|---|---|
| 0:00–0:35 | 1. The coordination blind spot | Business 1 | SDG impact, presentation |
| 0:35–0:55 | 2. Why SDG 11 needs this | Business 1 | SDG impact |
| 0:55–1:15 | 3. Atlas11: human-in-the-loop answer | CS 1 | innovation |
| 1:15–3:45 | 4. Live demo: proposal → review → memo → approval → map | CS 1 (demo) + CS 2 (narration) | innovation, technical |
| 3:45–4:25 | 5. Why the agent can be trusted | CS 2 | technical |
| 4:25–4:45 | 6. How Kiro engineered the result | CS 2 | technical/Kiro |
| 4:45–5:00 | 7. SDG 11 impact, scale, and close | Business 2 | SDG impact, presentation |

**Timing rule:** At 3:45, leave the live product and move to the evidence slides even if a click is late. The cached demo and video fallback exist to protect this boundary.

## 3. Slide-by-slide deck specification

### Slide 1 — “Urban funding is visible in silos; needs are not”
**Time:** 0:00–0:35  
**Speaker:** Business 1  
**Recommended visual:** A clean city-map silhouette split into three narrow “funder/project pipeline” streams on the left and one high-need district highlighted on the right. Avoid logos of funders unless a source is shown.

**On-slide copy (keep to this):**
> **Urban project coordination has two blind spots**  
> 1. Teams can unknowingly review similar proposals in parallel.  
> 2. High-need districts can remain invisible in fragmented project data.  
> **Atlas11 turns project evidence into a human-approved coordination decision.**

**Speaker notes:**
“City planners and development-finance teams make high-stakes coordination decisions across separate project pipelines. The problem is not that every similar project is wasteful. The problem is that teams do not have a consistent way to distinguish a true overlap from a project that is complementary — or to see where high local need is weakly matched by the visible project record. Atlas11 is a decision-support layer: it shows the evidence, recommends an action, and leaves the final coordination decision with a human.”

**Transition:** “This is exactly where SDG 11 gives us both the policy frame and the design constraints.”

---

### Slide 2 — “An operational lens for SDG 11”
**Time:** 0:35–0:55  
**Speaker:** Business 1  
**Recommended visual:** SDG 11 icon at center with target tags around it: 11.c primary; 11.3, 11.a/11.b, 11.1, 11.2, 11.5, 11.6 supporting.

**On-slide copy:**
> **Primary alignment: SDG 11.c**  
> Track and coordinate financial and technical assistance for sustainable, resilient urban development.  
> **Practical contribution:** transparent project coordination + district need/funding visibility.  
> **Human approval remains mandatory.**

**Speaker notes:**
“Atlas11 is primarily aligned with SDG target 11.c, which concerns support for sustainable and resilient buildings in least developed countries through financial and technical assistance. Its former indicator, 11.c.1, was deleted in the 2020 comprehensive review. We do not claim to recreate a UN indicator or to measure all aid. Instead, Atlas11 offers a local, auditable coordination view: what projects are visible in a given dataset, how a new proposal relates to them, and where a district-level need score and visible funding record suggest attention is needed. That also supports integrated planning under 11.a and 11.b and more transparent planning under 11.3.”

**Transition:** “Here is the product decision we designed around that principle.”

---

### Slide 3 — “AI finds evidence; people make the decision”
**Time:** 0:55–1:15  
**Speaker:** CS 1  
**Recommended visual:** Five-step horizontal flow: Proposal → Retrieve → Deterministic checks → Structured verdict/memo → Approver + gap map.

**On-slide copy:**
> **Atlas11 review loop**  
> 1. Submit a proposal  
> 2. Retrieve comparable funded projects  
> 3. Check place, time, outputs, and beneficiaries  
> 4. Produce a structured coordination memo  
> 5. Require an approver decision and record an audit trail

**Speaker notes:**
“Our key design decision is the boundary between facts and reasoning. Retrieval finds candidates. Deterministic tools establish canonical geography, a 12-month date-window rule, sector and output facts. The model then reasons only over those facts and returns structured JSON validated by Pydantic. The possible labels are Duplicate, Overlapping, Complementary, and Unrelated. A recommendation can guide coordination, but it cannot change funding; only an approver can approve or reject the recommendation, and that decision is logged.”

**Transition:** “We will now show the exact end-to-end path that the judges will evaluate.”

---

### Slide 4 — “Live demo: from proposal to coordination action”
**Time:** 1:15–3:45  
**Speaker:** CS 1 runs the interface; CS 2 narrates the meaning  
**Recommended visual:** No slide deck view; show the live application at 1366×768. Keep a small physical/second-screen timer visible to the team, not the judges.

**Visible demo outcomes:**
- A seeded demo proposal is clearly labelled as demo content.
- Review output contains **one `OVERLAPPING`** candidate and **one `COMPLEMENTARY`** candidate.
- The overlap recommendation is **`CO_FINANCE`** / coordinate — not automatic rejection or payment.
- A memo provides reasoning and candidate evidence.
- Switch to Approver role; perform the approval action.
- The gap map focuses a redirect/coordination target, without claiming that the target received funds.

**Narration principle:** Explain each result in one sentence. Do not read the UI.

**Fallback:** If the live page fails, immediately play the prerecorded 90-second video and say: “This is the same deterministic cached scenario, captured on the presentation device. Cached mode deliberately removes Bedrock and network dependence from the judged path.”

---

### Slide 5 — “Guardrails make the agent reviewable”
**Time:** 3:45–4:25  
**Speaker:** CS 2  
**Recommended visual:** Split panel: left “deterministic controls,” right “evidence and human control.”

**On-slide copy:**
> **Not keyword matching. Constrained, reviewable reasoning.**  
> - Canonical city/district IDs before names  
> - Inclusive implementation dates + exactly 12 months of slack  
> - Concrete outputs before text similarity  
> - `DUPLICATE` needs at least two matching attributes  
> - Pydantic-validated structured output; audit events; approver state machine

**Speaker notes:**
“A high similarity score alone never makes a project a duplicate. Atlas11 applies rules in order: geography first, time second, then concrete outputs and beneficiaries. Different cities cannot be Duplicate or Overlapping. Missing dates are conservative; the system does not infer a severe clash on incomplete time evidence. Duplicate requires at least two matching attributes or the result is downgraded and logged. These boundaries are testable even though an LLM itself is probabilistic. Our local evaluation history includes a 15-pair deterministic run at 100% accuracy, precision 1.00 for Duplicate, and hard-negative accuracy 1.00. We present that as a small evaluation-set result, not a general deployment guarantee.”

**Presenter cue:** If judges ask why `COMPLEMENTARY` matters, say: “It is the safeguard against treating similar language as duplication. A similar sector can still be a different corridor, phase, location, or beneficiary group.”

---

### Slide 6 — “Kiro was our engineering control plane”
**Time:** 4:25–4:45  
**Speaker:** CS 2  
**Recommended visual:** A compact “Kiro evidence chain” diagram: Steering → Specs → Tests → Hooks → Skills/Agents → Evidence. Use real repository screenshots in the final deck.

**On-slide copy:**
> **Kiro made the build deliberate and auditable**  
> Steering → Specs/EARS → task plans → properties/tests → hooks → skills & scoped agents → evidence  
> **We used Kiro to constrain quality, not just generate code.**

**Speaker notes:**
“We encoded the product, technology, structure, data honesty, and credit discipline in steering, so constraints travel with every task. We used different Kiro Spec workflows based on risk: design-first for the known data pipeline; requirements-first with EARS and property-based correctness for the clash agent; requirements-first for dashboard user flows; and a Quick Spec for the contained gap calculation. Hooks automate checks such as evaluation after prompt changes, secret protection before writes, schema-contract synchronization, and quality checks. Packaged skills support data ingest, evaluation, impact analysis, and rehearsal; scoped custom agents separate data-only work from read-only judge simulation. This gives us reproducible evidence, not a black-box coding story.”

**Important:** Only show a feature as “used” if the team can show its local artifact, screenshot, or command output. See Section 7 for the evidence checklist.

---

### Slide 7 — “Coordinate better, measure honestly, scale responsibly”
**Time:** 4:45–5:00  
**Speaker:** Business 2  
**Recommended visual:** One simple map panel + three close statements. Do not put a dense metrics table on this slide.

**On-slide copy:**
> **Atlas11 makes coordination evidence actionable**  
> **Today:** reviewable clash decisions and visible local gaps  
> **Next:** ingest more sourced funder datasets with the same schema  
> **Always:** human sign-off, clear provenance, no claim of automatic funding

**Speaker notes:**
“Our local project snapshot covers 323 urban projects and US$49.94 billion in recorded commitments, all World Bank records; it also reveals a data-quality limitation — 89% of those records have no city tag. That is why Atlas11 keeps provenance visible and treats data completeness as a finding, not something to hide. The same pipeline can normalize additional sourced data, but we will never inflate what the current snapshot proves. Atlas11’s goal is straightforward: make project coordination and under-served-district questions visible early enough for humans to act. Thank you — we welcome your questions.”

## 4. Scripted 2.5-minute live demo runbook

### Precondition
Use the canonical deterministic scenario documented in the project Specs:

- `DEMO_MODE=cached`
- Scenario key: `demo-city-transit-01`
- Proposal ID: `demo-proposal-01`
- Expected verdicts: one `OVERLAPPING`, one `COMPLEMENTARY`
- Expected memo recommendation: `CO_FINANCE`
- Expected action: approver approval and a local map/redirect focus response

If implementation identifiers differ, use the IDs exposed by the application, but do **not** change the spoken outcomes above without verifying the cache payload first.

### Live demo script

| Clock | Operator action | CS 1 says | CS 2 says / points out |
|---|---|---|---|
| 1:15–1:30 | Open the proposal form; reveal the seeded scenario badge and submit. | “We submit one new transit proposal. This demo record is visibly seeded so we do not confuse it with sourced project data.” | “The frontend, API, and cache share stable proposal and review identifiers.” |
| 1:30–1:50 | Show review progress / agent trace. | “The agent first retrieves comparable projects.” | “The trace exposes tool calls. Those tools establish facts; the model does not invent date or geography math.” |
| 1:50–2:15 | Select the `OVERLAPPING` verdict. | “This result shares location and period with part of an existing project’s scope, so Atlas11 recommends coordination or co-finance.” | “That is overlap, not a duplicate: it is a human coordination question.” |
| 2:15–2:35 | Select the `COMPLEMENTARY` verdict. | “This is deliberately a look-alike. It sounds similar, but the corridor, phase, location, or beneficiaries differ.” | “The Complementary label is how we avoid false duplication from text similarity.” |
| 2:35–2:55 | Open memo. | “The memo compresses evidence into an action-ready recommendation.” | “The structured memo preserves the candidate reference and rationale for review.” |
| 2:55–3:15 | Toggle role to Approver and approve. | “Only an approver can sign off; a planner cannot bypass the state machine.” | “Approval is coordination sign-off. No money moves in Atlas11.” |
| 3:15–3:40 | Open/focus the gap map redirect target. | “The map now focuses the district suggested for coordination attention.” | “This is not a claim that money was allocated. It is a decision-support redirect based on local need and visible funding data.” |
| 3:40–3:45 | Exit demo. | “The entire scripted path is cached for resilience.” | “Now, the engineering controls behind the demo.” |

### Operator discipline

- Prepare browser zoom and window size at **1366×768**.
- Use a hard-refresh before judges enter, then do not refresh in the demo.
- Do not expose `agent/.env`, AWS console, terminals containing credentials, or internal logs.
- If any visible record is seeded, preserve the seeded badge and say so aloud once.
- If the reviewer output does not immediately render, move directly to the prerecorded video; do not debug live.

## 5. Product and technical architecture talk track

### One-sentence architecture
“Atlas11 is a React/TypeScript dashboard over a FastAPI service, with a Strands-based Bedrock Nova Pro review agent constrained by local deterministic tools, Pydantic schemas, SQLite audit/state data, Chroma retrieval, and a cached offline demo path.”

### Architecture diagram contents for an appendix or backup slide

```text
Planner dashboard (React + Vite + TypeScript + Leaflet)
            │ REST / JSON + review events
            ▼
FastAPI API — typed Pydantic request/response models
            │
            ├── SQLite: proposals, approvals, audit records
            ├── Cached demo response: data/demo_cache/ (offline demo path)
            └── Clash review service
                  ├── Retrieval: Chroma in data/index/
                  ├── Embeddings: Bedrock Titan V2 or local MiniLM fallback
                  ├── Deterministic tools: similar projects, project facts,
                  │   geography/time/output overlap facts, district need, memo
                  └── Strands Agent + Amazon Bedrock Nova Pro
                        structured JSON → Pydantic validation → taxonomy guardrails
```

### Technical claims the CS presenters can explain

| Design choice | Why it matters | Judge-ready sentence |
|---|---|---|
| Structured Pydantic contracts | Prevents free-form model text from becoming an API response. | “The model’s output is validated against a typed schema before it reaches the user.” |
| Deterministic `check_overlap` facts | Keeps geography/time math outside model improvisation. | “The LLM reasons about verified facts; it does not decide how dates or canonical IDs are computed.” |
| Taxonomy validator | Constrains severity and records corrections. | “A Duplicate requires at least two matching attributes; otherwise we downgrade and audit it.” |
| Approval state machine | Maintains human authority. | “A review becomes reviewed, then only an approver may approve or reject; rejection requires a reason.” |
| SQLite audit trail | Supports reviewability. | “Tool calls, verdicts, and approval actions are timestamped audit events.” |
| Chroma + provider boundary | Enables similar-project retrieval with local fallback. | “The pipeline can select Bedrock embeddings or a local MiniLM fallback through configuration.” |
| Cached demo path | Makes the judged flow resilient. | “Cached mode serves the fixed scenario without Bedrock; it is a designed reliability feature, not a hidden mock.” |
| 20-second Bedrock boundary / clear expiry handling | Prevents a cloud failure from becoming a stack trace. | “If workshop credentials expire, the system should surface a readable refresh instruction, not pretend the agent is broken.” |

## 6. SDG 11 alignment — detailed, defensible framing

### Primary: Target 11.c
**Target framing:** SDG 11.c concerns supporting least developed countries, including through financial and technical assistance, in building sustainable and resilient buildings using local materials. The SDG metadata history records that indicator 11.c.1 was deleted in the 2020 comprehensive review.

**Atlas11 contribution:** Atlas11 does not claim to restore the UN indicator, track all assistance, or prove outcomes. It provides a local decision-support mechanism for tracking visible project records, surfacing potential coordination relationships, and recording human coordination decisions. This is an operational complement to the measurement gap, not a replacement for official SDG measurement.

### Supporting targets

| Target | Honest Atlas11 linkage | What not to claim |
|---|---|---|
| 11.3 — inclusive and sustainable urbanization / participatory planning | Visible rationale, audit trails, and human approval support transparent planning processes. | Do not claim public participation is implemented unless the application includes it. |
| 11.a — links across urban, peri-urban, and rural planning | Cross-project visibility can support integrated planning across agencies and jurisdictions. | Do not claim coordination outcomes have occurred without evidence. |
| 11.b — integrated policies for inclusion, resource efficiency, climate adaptation, disaster resilience | The taxonomy and need layer can make resilience-relevant projects and needs easier to compare. | Do not claim resilience outcomes or policy adoption. |
| 11.1 — housing/basic services and slum upgrading | Informal-settlement share is one potential need-score input where sourced and quality-labelled. | Do not treat an illustrative input as official 11.1.1 reporting. |
| 11.2 — accessible sustainable transport | Transport-access gap can be a local need-score input. | Do not claim service/access improvements without measured outcome data. |
| 11.5 — disaster-risk loss reduction | Flood exposure can be a local need-score input. | Do not claim reduced losses. |
| 11.6 — reduced environmental impact | Project taxonomy can tag water, waste, and environmental themes for visibility. | Do not claim emissions, air-quality, or waste outcomes without outcome data. |

### Current local evidence to state precisely

Run from repository root before final rehearsal:

```zsh
source .venv/bin/activate && python .kiro/skills/impact-brief/scripts/impact_stats.py
```

**Observed output at preparation time (local `data/processed/projects.csv`):**

- **323 urban projects**; source: local `projects.csv`.
- **World Bank: 323**; the current snapshot is a single-funder dataset.
- **US$49.94B total recorded commitments**; computed from this local file.
- **289 projects (89%) have no city tag**; frame this as an important data visibility/quality finding.
- **One gap district:** `Atlas11 Demo District High`, need score `1.00`, **quality: illustrative**. Do not present this as a measured real-world finding.

### Sources for the final slide appendix

- UN Sustainable Development Goal 11 overview: <https://sdgs.un.org/goals/goal11>
- UN SDG indicator metadata / indicator list: <https://unstats.un.org/sdgs/metadata/>
- Local dataset computation: `data/processed/projects.csv`, via `.kiro/skills/impact-brief/scripts/impact_stats.py`.
- Local need-score provenance and weights: `data/geo/need_scores.csv`, `data/geo/district_indicators.csv`, `data/geo/need_weights.json`.

## 7. “How we used Kiro” — evidence-backed presentation content

### The one-slide version
> **Kiro was our build system for reliable AI software:**  
> **Steering** encoded product, SDG, data-honesty, architecture, and cost constraints.  
> **Specs** converted requirements into reviewed tasks.  
> **EARS + property tests** made deterministic safety rules testable.  
> **Hooks** automated quality, evaluation, security, and contract checks.  
> **Skills + scoped agents** packaged repeatable expertise and least privilege.  
> **Evidence artifacts** made our process inspectable.

### What to show in a 20-second Kiro segment

1. **Steering panel / repository tree:** show `.kiro/steering/` and explain that `tech.md`, `structure.md`, `product.md`, `credit-discipline.md`, and `data-honesty.md` make constraints persistent.
2. **Spec artifact:** show a requirements/design/tasks view for `clash-agent`. Point to requirements-first work, deterministic taxonomy constraints, and state-machine requirements.
3. **Correctness evidence:** show a Hypothesis property or task entry — for example cross-city candidates cannot result in `DUPLICATE`/`OVERLAPPING`, and Duplicate requires at least two matching attributes.
4. **Hook inventory:** show `.kiro/hooks/`, then one readable hook configuration or execution result. Do not attempt to explain all hooks live.
5. **Evidence data:** show `.kiro/evidence/eval-history.csv` and quote the small-set evaluation with the scope disclaimer.

### Feature-by-feature evidence map

| Kiro capability | Repository evidence | What to say | Status wording |
|---|---|---|---|
| Always steering | `.kiro/steering/product.md`, `tech.md`, `structure.md`, `credit-discipline.md` | “Persistent product and engineering boundaries follow every task.” | Present if files exist. |
| Auto data-honesty steering | `.kiro/steering/data-honesty.md` | “Data provenance and illustrative-data labelling are not optional reminders.” | Present if file exists. |
| File-match / manual steering | Relevant steering front matter and documented commands | “Relevant context loads when we work in the matching area or invoke a focused workflow.” | Show only if configured and visible. |
| Folder-scoped rules | `agent/AGENTS.md` | “The backend has its own local operating rules, including credential and schema discipline.” | Present if file exists. |
| Design-first Spec | `.kiro/specs/data-pipeline/` | “We started from a known architecture — data, embeddings, index, retrieval — then derived work.” | Present; distinguish task completion from plan existence. |
| Requirements-first Spec | `.kiro/specs/clash-agent/`, `.kiro/specs/planner-dashboard/` | “We locked user and safety requirements before implementation.” | Present; distinguish task completion from plan existence. |
| Quick Spec | `.kiro/specs/gap-finder/` | “The deterministic gap calculation was narrow enough for a leaner Spec workflow.” | Present. |
| EARS requirements | `docs/SPEC_PROMPTS.md`; clash-agent requirements | “We used WHEN/THEN rules to turn safety behavior into testable contracts.” | Present if requirements artifact is shown. |
| Property-based correctness | clash-agent and gap-finder task plans; test files under `agent/tests/` | “We test invariants around the model: taxonomy boundaries, score ranges, retrieval order, and approval transitions.” | Say “specified and tested” only after executing/presenting test results. |
| Hooks | `.kiro/hooks/` — `prompt-eval`, `secret-guard`, `schema-contract`, `code-quality`, etc. | “Automated hooks convert quality and security rules into repeatable checks.” | Present as configured; show a run result if claiming active use. |
| Skills | `.kiro/skills/{worldbank-ingest,clash-eval,impact-brief,demo-rehearsal}` | “Repeatable expertise is packaged so the workflow is not dependent on memory.” | Present. |
| Custom agents | `.kiro/agents/data-steward.md`, `.kiro/agents/judge-simulator.md` | “We separated data-only permissions from independent read-only judging.” | Present. |
| MCP / Powers | `.kiro/settings/mcp.json`; Kiro panel evidence if available | “We used documentation/browser/data integrations only where they added verified context.” | Do not say they were exercised without a screenshot/log. |
| Evaluation evidence | `.kiro/evidence/eval-history.csv` | “Prompt/evaluation iterations are recorded rather than asserted.” | Present with small-set disclaimer. |

### Hooks to mention — select three, not nine

- **`secret-guard.json`:** blocks accidental writes that contain AWS keys — security by construction.
- **`prompt-eval.json`:** reruns/records evaluation around prompt changes — prompts are treated as versioned engineering assets.
- **`schema-contract.json`:** protects alignment between backend Pydantic contracts and frontend types.

**Additional configured hooks:** `aws-expiry-watch`, `checkpoint-on-stop`, `code-quality`, `data-reindex`, `prompt-log-on-submit`, and `verify-spec-task`. Keep these in backup material rather than cramming them into the main 5 minutes.

### The honest implementation-status answer
The current task plans show a mixture of completed (`[x]`), in-progress (`[~]`), and uncompleted (`[ ]`) tasks. Never describe a planned item as shipped. On stage, speak from the actual running demo and completed artifacts. If asked about the task plan, answer: “We use it as a transparent engineering ledger. It shows what is completed, what is in progress, and what remains — that is more credible than hiding unfinished work.”

## 8. Team roles and handoffs

### Recommended assignment

| Team member | Discipline | Main responsibility | Speaking time | Backup duty |
|---|---|---|---:|---|
| Business 1 | Business | Problem framing, stakeholder value, SDG policy frame | 0:00–0:55 | Starts video fallback if CS 1 loses demo state |
| CS 1 | Computer Science | Product demo operator, proposal/review flow | 0:55–3:15 | Explains architecture if CS 2 is interrupted |
| CS 2 | Computer Science | Demo narration, agent guardrails, Kiro evidence | 3:15–4:45 | Takes over product navigation / cache fallback |
| Business 2 | Business | Impact integrity, scale, conclusion, Q&A timekeeper | 4:45–5:00 | Owns Q&A on impact, data provenance, stakeholders |

### Handoff lines

- **Business 1 → CS 1:** “We designed Atlas11 so that the next step is a reviewable decision, not another dashboard. Here is the workflow.”
- **CS 1 → CS 2 (during demo):** “The interface is fast because the intelligence is structured. [CS 2] will show the controls that keep it honest.”
- **CS 2 → Business 2:** “Technical reliability matters only if it advances a real planning decision. [Business 2] will close with what we can — and cannot — claim.”

### Q&A positioning by person

- Business 1: user need, adoption, stakeholder process, SDG policy framing.
- CS 1: data flow, retrieval, cache, frontend/API interaction.
- CS 2: agent logic, testing, Kiro, hooks, security, evaluation.
- Business 2: impact numbers, data provenance, scale, limitations, commercial/operating model.

## 9. Two-minute Q&A — priority answers

Use a short answer first; elaborate only if invited. The timekeeper gives a 20-second warning at 1:40.

### Q1. “How is this more than semantic search?”
**Answer:** “Semantic retrieval only supplies candidates. Atlas11 then checks canonical geography, implementation timing with an explicit 12-month rule, concrete outputs, and beneficiaries. The model returns a structured verdict, then a validator applies taxonomy rules. High text similarity alone cannot create a Duplicate verdict.”

### Q2. “What stops hallucinated or unsafe recommendations?”
**Answer:** “Facts come from deterministic tools, output must validate against Pydantic schemas, severity constraints are applied after the model, and an approver must sign off. Tool calls, verdicts, and approval actions are recorded in the audit trail. In the demo, cached responses are deliberately deterministic.”

### Q3. “What real SDG impact have you proven?”
**Answer:** “We have proven a prototype workflow and local visibility metrics, not downstream development outcomes. Our local snapshot has 323 World Bank projects and exposes 89% without city tags; that data completeness issue is itself important. We frame Atlas11 as decision support for SDG 11 coordination, not as evidence that funding has already been reallocated.”

### Q4. “Why is 11.c the right target?”
**Answer:** “11.c concerns financial and technical support for sustainable and resilient urban development, and its former indicator was deleted in the 2020 review. Atlas11 does not recreate the official indicator. It supplies a local, auditable way to make project-assistance coordination and visible gaps easier to review.”

### Q5. “How did Kiro make a technical difference?”
**Answer:** “We used Kiro to encode constraints in steering, formalize risk-sensitive requirements in Specs and EARS, capture testable invariants with property-based tests, automate checks through hooks, and package repeatable work in skills and scoped agents. The proof is in the repository artifacts and evaluation history, not in a claim that AI wrote everything.”

### Q6. “Can this scale beyond your current data?”
**Answer:** “The schema and rebuildable ingestion/indexing pipeline are designed to accept additional sourced datasets. We would scale only by preserving source URLs, funder attribution, canonical place IDs, snapshot dates, and explicit data-quality flags. We will not merge incomparable data and pretend it is complete.”

## 10. Extended judge-question bank

| Judge question | Concise answer | Evidence to show if asked |
|---|---|---|
| “What does `OVERLAPPING` mean versus `DUPLICATE`?” | “Overlap means partial shared scope, location, period, outputs, or beneficiaries and usually calls for coordination. Duplicate means substantially the same result would be funded twice; it needs stronger evidence, including at least two matching attributes.” | `sdg11-domain.md`; clash-agent Spec. |
| “Why do you need an LLM at all?” | “Deterministic code filters and calculates facts; the LLM synthesizes nuanced evidence into a readable classification and memo across heterogeneous project descriptions. It is constrained by schemas, rules, and human approval.” | Architecture diagram; prompt/tool interfaces. |
| “Could a planner game the recommendation?” | “The system is not an authorization platform, but it records actor/role, proposal/review IDs, and audit events. In a production deployment we would add authenticated identity, role management, and independent data governance.” | SQLite/audit specification; non-goals. |
| “What happens when AWS credentials expire?” | “The design maps expiry to a readable refresh message, and the judged scenario runs in cached mode without Bedrock. We also keep a local video fallback.” | Tech steering; demo checklist. |
| “Why should anyone trust an illustrative district score?” | “They should not treat it as measured evidence. We explicitly label it illustrative. The product’s value is also the data-quality discipline: it makes the provenance and limitation visible.” | `need_scores.csv`; data-honesty steering. |
| “What is your current model accuracy?” | “The latest recorded small evaluation result is 15/15 on a local, deterministic golden-pair set, with duplicate precision and hard-negative accuracy both 1.00. That is not a deployment claim; it is a regression guard on a limited labelled set.” | `.kiro/evidence/eval-history.csv`. |
| “How do you prevent bias?” | “We do not claim to eliminate it. We reduce unreviewed model discretion with deterministic controls, source/provenance fields, conservative uncertainty handling, human approval, auditability, and a plan to evaluate representative local data before deployment.” | Taxonomy rules; audit/approval design. |
| “What happens if there is no city tag?” | “We avoid inferring a city. Missing geography weakens matching and becomes a visible data-quality limitation. In the current local snapshot, 289 of 323 projects lack city tags.” | Impact script output. |
| “Does approval trigger funding?” | “No. Approval is coordination sign-off only. Atlas11 never moves money or allocates a budget.” | Product constraints; approval rules. |
| “What would you build next?” | “First, add high-quality, sourced multi-funder records and canonical location mapping; second, expand labelled evaluation pairs; third, add authenticated roles and operational governance; fourth, validate user value with planners.” | Roadmap below. |

## 11. Demo setup, contingency, and rehearsal checklist

### 30 minutes before

- [ ] Run the impact script and update any locally computed slide numbers.
- [ ] Confirm `DEMO_MODE=cached` is active for the demo path.
- [ ] Verify the canonical scenario generates exactly the expected `OVERLAPPING` and `COMPLEMENTARY` outputs.
- [ ] Confirm the Approver role and approval flow work locally.
- [ ] Confirm map state or screenshot; map tiles are the only acceptable network-dependent visual. If tiles fail, use the screenshot/video fallback.
- [ ] Open the prerecorded demo video locally; test sound off and on.
- [ ] Close all credential files, terminals, editor tabs containing secrets, chats, and notifications.
- [ ] Set browser to 1366×768 equivalent; zoom UI only if it remains legible.
- [ ] Have a PDF export of the final deck on the presenting computer.

### Five minutes before

- [ ] Open live app to the starting form; do not pre-submit the proposal.
- [ ] Put a copy of the architecture and Kiro evidence slides in a backup deck section.
- [ ] Confirm each speaker’s first line and handoff line.
- [ ] Business 2 starts a silent 5:00 timer.
- [ ] Switch off notification banners and sleep mode.

### Contingency matrix

| Failure | Immediate action | Spoken recovery line |
|---|---|---|
| Live review does not load in 5 seconds | CS 2 starts prerecorded video; CS 1 narrates. | “We designed the judged path with a deterministic local cache; this recording shows the same cached scenario.” |
| Bedrock/AWS error | Stay in cached mode; do not troubleshoot credentials. | “Live cloud access is secondary in the demo; the resilience requirement is that cached review remains locally available.” |
| Map tiles are blank | Continue with data panel or video/screenshot map. | “Map tiles are visual only; the district record and coordination target are locally backed.” |
| Wrong browser tab / UI state | Jump to video or use the static demo screenshots. | “To protect time, we will show the recorded end-to-end result and move to the controls behind it.” |
| Speaker loses place | Next speaker uses their first transition line and proceeds. | “The important point is…” |
| Time overrun at 3:45 | Stop the live demo, move to Slide 5. | “The remaining steps are captured in the audit trail; here is why the recommendation is constrained.” |

### Two full rehearsals

**Rehearsal 1: correctness**
- Every click works; each claimed visual is present.
- Replace unsupported claims with honest wording.
- Record actual time; remove explanations, not essential evidence.

**Rehearsal 2: failure mode**
- Force the video fallback.
- Practice a judge interrupting during the demo.
- Time Q&A answers at 15–25 seconds each.

## 12. Evidence and screenshot capture list

Create a small, clean evidence folder for deck visuals; do not capture credentials or personally identifiable information.

| Needed visual | Source / command | Why it matters |
|---|---|---|
| End-to-end demo state | Browser screenshot after cached review | Proves the product flow. |
| Overlap vs complementary result | Browser screenshot with both verdict cards | Proves the core taxonomy distinction. |
| Memo + approver action | Browser screenshot | Proves human-in-the-loop control. |
| Gap map / illustrative label | Browser screenshot | Proves the redirect is visualized without a funding claim. |
| Kiro Specs page / `tasks.md` | `.kiro/specs/clash-agent/tasks.md` | Proves Spec-driven workflow and transparent delivery ledger. |
| Kiro hook configuration | `.kiro/hooks/secret-guard.json` or `prompt-eval.json` | Proves quality/security automation. |
| Evaluation history graph/table | `.kiro/evidence/eval-history.csv` | Proves recorded regression evidence. |
| Skills and agent tree | `.kiro/skills/`, `.kiro/agents/` | Proves reusable expertise and least privilege. |
| Local impact output | Run the command below and screenshot the result | Proves exact local metric provenance. |

```zsh
source .venv/bin/activate && python .kiro/skills/impact-brief/scripts/impact_stats.py
```

**Recommended hidden appendix slides:** architecture; Kiro evidence matrix; dataset/data-honesty statement; full Q&A bank; sources.

## 13. Roadmap — say only if asked

1. **Data quality first:** add sourced city/district metadata and multi-funder records; preserve provenance, source URLs, snapshot dates, and quality labels.
2. **Evaluation first:** grow the human-labelled golden-pair set across cities, sectors, periods, languages, and hard negatives; measure error by class before broadening automation.
3. **Governance first:** add authentication, role management, review queues, exportable audit reports, retention rules, and local institutional oversight.
4. **User research first:** test whether planners understand and act on the memo, map, and confidence/rationale — rather than optimizing model scores in isolation.
5. **Only then scale:** expand ingestion through documented adapters and build per-city indicator governance with local partners.

## 14. Final presenter checklist

- [ ] We can state Atlas11’s value in one sentence without claiming it allocates money.
- [ ] We can explain `OVERLAPPING` versus `COMPLEMENTARY` without saying “the model just knows.”
- [ ] We use “illustrative” for the current demo district need score.
- [ ] We state that the current 323-project snapshot is World Bank-only and that 89% lack city tags.
- [ ] We describe local evaluation metrics as a limited regression dataset result, not a universal accuracy claim.
- [ ] We can show three concrete Kiro artifacts: a Spec, a hook, and an evidence/skill/agent artifact.
- [ ] We use the cached demo and video fallback deliberately, not apologetically.
- [ ] Every team member knows their 15–25 second answer to one technical and one impact question.
- [ ] We finish the final slide by 5:00 and reserve the remaining 2:00 for judges.

---

## Appendix: concise sources and local provenance

- Product, taxonomy, non-goals, SDG framing: `.kiro/steering/product.md`, `.kiro/steering/sdg11-domain.md`.
- Spec workflows, EARS requirements, property-test objectives, cached demo contract: `docs/SPEC_PROMPTS.md`, `.kiro/specs/`.
- Kiro feature plan and build evidence guidance: `PLAYBOOK.md`.
- Hook inventory: `.kiro/hooks/`.
- Skill inventory: `.kiro/skills/`.
- Custom agents: `.kiro/agents/data-steward.md`, `.kiro/agents/judge-simulator.md`.
- Evaluation record: `.kiro/evidence/eval-history.csv`.
- Local data metric computation: `.kiro/skills/impact-brief/scripts/impact_stats.py` over `data/processed/projects.csv`.
- Need-score source/quality: `data/geo/need_scores.csv`, `data/geo/district_indicators.csv`, `data/geo/need_weights.json`.
- Official SDG context: [UN SDG 11](https://sdgs.un.org/goals/goal11), [UN SDG metadata](https://unstats.un.org/sdgs/metadata/).

*All externally sourced context above is summarized for presentation use. Local data results must be recomputed immediately before presenting if the underlying dataset changes.*
