# Atlas11: Kiro build playbook (HKBU × AWS BUild Agentic AI Hackathon 2026)

**Goal:** win on all four 25-point criteria by building Atlas11 (the SDG 11 clash and gap agent) with deliberate, explainable use of **every** Kiro feature.

**Files in this pack:**

| Path | What it is |
|---|---|
| `PLAYBOOK.md` | This file: setup, credit plan, build-day runbook, pitch |
| `docs/SPEC_PROMPTS.md` | The 5 spec prompts + EARS/property review checklists |
| `.kiro/steering/` | 13 steering files covering all 4 inclusion modes + a file reference |
| `.kiro/skills/` | 4 Agent Skills (ingest, eval, impact, rehearsal), 3 with runnable scripts |
| `.kiro/hooks/` | 7 hook files (8 hooks): file-save, pre/post tool use, stop + confirm, command and agent actions |
| `docs/hooks-to-verify/` | 2 hooks whose trigger names need confirming on your Kiro version |
| `.kiro/agents/` | 2 custom agents: `judge-simulator` (read-only subagent), `data-steward` |
| `.kiro/settings/mcp.json` | AWS docs, Playwright and a **custom** `atlas11-data` MCP server |
| `agent/AGENTS.md` | Folder-scoped rules (Kiro loads subdirectory AGENTS.md) |
| `scripts/hooks/` | Hook helper scripts (tested; no-ops until the code they call exists) |
| `scripts/mcp/atlas11_data_server.py` | The custom MCP server |
| `data/` | Need weights, golden-pair template |

---

## 1. Kiro feature coverage matrix (this is your Technical Implementation score)

The judges ask: *"Does the team clearly explain **why and how** they used specific Kiro functionalities?"* Every row has a reason. At the end, `/pitch-evidence` turns this into `docs/kiro-usage.md` with real evidence.

| Kiro feature | Where and how we use it | Why (the line for judges) | Criterion |
|---|---|---|---|
| **Vibe chat** | Quick questions, scaffolding `npm create vite`, exploring Strands APIs | Fast exploration where a spec would be overkill | Tech |
| **Steering: always** | `product.md`, `tech.md`, `structure.md`, `credit-discipline.md` | Every generated line knows the product, stack and layout | Tech |
| **Steering: fileMatch** | `sdg11-domain.md` (agent/data), `agent-guardrails.md` (agent), `frontend-design.md` (frontend), `aws-credentials.md` | Domain rules load only where relevant, so context stays lean | Tech, SDG |
| **Steering: auto** | `data-honesty.md` loads whenever data or metrics are touched | Integrity rules apply without anyone remembering to add them | SDG, Pres |
| **Steering: manual (slash commands)** | `/handoff`, `/demo-readiness`, `/pitch-evidence`, `/sync-docs` | Repeatable on-demand workflows (the IDE 1.x replacement for manual hooks) | Tech |
| **Steering file references** | `#[[file:data/geo/need_weights.json]]` inside `sdg11-domain.md` | One source of truth: steering reads the live config | Tech |
| **AGENTS.md (subfolder)** | `agent/AGENTS.md` | Folder-scoped rules for the agent service | Tech |
| **Spec: Design-First** | Spec A `data-pipeline` | The architecture was known, so we started from design | Tech |
| **Spec: Requirements-First + EARS** | Specs B and C | Safety rules and UX pinned down as testable statements | Tech, Innov |
| **Correctness (property-based tests)** | Spec B properties (taxonomy invariants, approval state machine), Spec D | The LLM can't be unit-tested, but every rule around it can. Shrunk counterexamples are proof | Tech |
| **Quick Spec** | Spec D `gap-finder` | Small and well understood, so no approval gates | Tech |
| **Bugfix Spec** | Spec E, created from a real failure | Root cause + regression guard, recorded in `bugfix.md` | Tech |
| **Task execution** | ⚡ one task at a time (lab advice), Supervised → Autopilot | Controlled progress and fewer wasted credits | Tech |
| **Hooks: File Save + command** | Reindex on data change; **eval on prompt change**; ruff; tsc | Quality gates that cost zero credits | Tech, Innov |
| **Hooks: File Save + agent prompt** | `schema-contract-sync` | Keeps frontend types in sync with the Pydantic contract | Tech |
| **Hooks: Pre Tool Use (blocking)** | `secret-guard` blocks writes containing AWS keys | Security by construction | Tech |
| **Hooks: Post Tool Use** | `aws-expiry-watch` spots expired workshop credentials | Stops the agent "fixing" working code when credentials expire | Tech |
| **Hooks: Agent Stop + confirm** | `git-checkpoint` | Every turn can become a clean commit, so any account can resume | Tech |
| **Hooks: Prompt Submit, Post Task Execution** | `docs/hooks-to-verify/` | Auto-captured prompt evidence and an acceptance check per task | Tech |
| **MCP (workspace config)** | `aws-docs` for Bedrock and Strands docs; `playwright` for UI screenshots and demo checks | Live, correct docs and real browser verification | Tech |
| **Custom MCP server** | `atlas11-data` exposes our dataset to Kiro | Kiro looks up real projects while labelling and debugging | Tech, Innov |
| **Kiro Powers** | **Strands** Power (installed from the panel) | Loads only when agent code is discussed, so it doesn't bloat context like an always-on MCP | Tech |
| **Agent Skills** | `worldbank-ingest`, `clash-eval`, `impact-brief`, `demo-rehearsal` | Packaged, repeatable know-how with scripts, invoked by `/name` or automatically | Tech, Pres |
| **Custom agents** | `data-steward` (writes only under `data/`) | Least privilege: data work can't break app code | Tech |
| **Subagents** | `judge-simulator` run as a read-only subagent; rubric scoring + Q&A drill | An independent reviewer that hasn't seen the work being produced | Pres |
| **Built-in Plan agent** | One planning pass over steering + spec prompts at kickoff | Catch scope risks before spending credits | Tech |
| **Context providers** | `#spec`, `#steering`, `#file`, `#terminal`, `#problems`, `#git diff`, `#codebase`, `#mcp`, `#url` | Precise context means fewer tokens and better output | Tech |
| **Checkpoints / Restore** | Roll back a bad task instead of prompting it to fix itself | Cheaper and cleaner than repair loops | Tech |
| **Autopilot vs Supervised** | Supervised for the agent core and first tasks; Autopilot for UI once tests are green | Human control where risk is highest | Tech |
| **Terminal integration: Run / Run and Trust** | Trust `pytest`, `npm run`, `ruff`, `python scripts/*` | Fewer interruptions, while dangerous commands still need approval | Tech |
| **Model picker** | Per-phase model choice (see §2) | Credits spent where reasoning matters | Tech |

---

## 2. Credit plan: 4 accounts × 1,000 credits, used one after another

The accounts are used **sequentially on the same project folder**: when one runs low, sign in with the next. This isn't a split of work between people. Everything that matters (specs, `tasks.md` status, steering, hooks, skills, code) lives **in the repo**, so it carries over between accounts. Only chat history doesn't.

### Account switch protocol
1. Switch when the current account has **about 80 credits left**, at a **task boundary**. Never switch mid-task.
2. Run `/handoff`. It writes `.kiro/evidence/HANDOFF.md` and commits.
3. Sign out of Kiro and sign in with the next account. Open the **same folder**.
4. Re-check that the **Strands Power** is installed. Powers live in `~/.kiro/powers`, so they may be per-profile. MCP servers come from the workspace `mcp.json` and need no action.
5. First prompt on the new account: `#file:.kiro/evidence/HANDOFF.md #spec <current-spec> Continue from the next step.`
6. Log it: add a row to `.kiro/evidence/credit-log.md` (account #, credits at start/end, phase).

### Where the 4,000 credits go (target split)
| Phase | Share | Notes |
|---|---|---|
| Kickoff: Plan agent pass, steering check, Power/MCP setup | 3% | |
| Spec A data-pipeline | 12% | |
| **Spec B clash-agent** (incl. PBT + eval iterations) | **30%** | The heart of the build. Spend here |
| Spec C planner-dashboard | 20% | |
| Spec D gap-finder (Quick Spec) | 5% | |
| Spec E bugfix(es) | 8% | |
| Demo hardening: `/demo-readiness`, Playwright screenshots, judge-simulator, `/pitch-evidence` | 10% | |
| **Untouched reserve** (last ~200 credits on the last account) | 12% | Emergency fixes on stage day only |

### Rules that save the most credits
- **Model choice.** Multipliers below are from kiro.dev/docs/models today. The event's Kiro build may list different models, so check the picker.
  - **Auto (1.0x)** is the default for task execution.
  - **Claude Sonnet (1.3x)** only for Spec B requirements and design, and for hard debugging after Auto fails twice.
  - Low-multiplier models (e.g. Haiku 4.5 at 0.4x, Qwen3 Coder Next at 0.05x) for `/sync-docs`, boilerplate and renames.
  - **Avoid Opus-class models (2x+)** unless the reserve is untouched and you're truly stuck.
- **Command hooks are essentially free; agent-prompt hooks cost credits.** That’s why 7 of the 8 hooks enabled in this pack are shell commands.
- **Review specs before moving phases.** Editing a requirement costs one prompt; repairing generated code costs many.
- **Restore a checkpoint** instead of asking Kiro to repair a bad task.
- **One task at a time.** "Run all tasks" builds waves of concurrent tasks, which is fast but hard to stop when a wave goes wrong.
- Steering `credit-discipline.md` tells the agent to make minimal diffs, run narrow tests and stop after each task.

---

## 3. Before the event (prepare data and config, not app code)

> **Ask the organisers** whether pre-written application code is allowed. Preparing data, config and steering is almost certainly fine. This pack contains no app code; Kiro generates all of it on the day through specs.

- [ ] Install on the **presenting laptop**: Kiro, Python 3.11+, `uv`, Node 20+, git. Run `uv --version` (the labs need it for MCP).
- [ ] `git init` a repo, copy this pack in, and commit.
- [ ] Check your Kiro version (Help → About), then open `.kiro/hooks` in the Agent Hooks panel and confirm all 7 files load. If any don't, ask Kiro: *"Recreate the hooks described in .kiro/hooks/*.json for this Kiro version."* Do the same for `docs/hooks-to-verify/`, then move them into `.kiro/hooks/` once the trigger names are confirmed (the workshop's Kiro build may be older than kiro.dev's docs).
- [ ] Install the **Strands Power** (Kiro Ghost ⚡ icon → *Build an agent with Strands* → Install). Check that MCP servers `aws-docs`, `playwright` and `atlas11-data` show **Connected**.
- [ ] **Fetch the data:** `python .kiro/skills/worldbank-ingest/scripts/fetch_worldbank.py --countries PK BD --out data`
- [ ] Choose the **demo city** (Karachi is a strong option, e.g. the World Bank's KWSSIP-2 water/sewerage project P171422 plus BRT corridors funded by different lenders). **Verify every project you mention** on the funder's own site.
- [ ] Download district boundaries (e.g. HDX admin boundaries) to `data/geo/districts.geojson`, and fill `district_indicators.csv` with `indicator_quality` honestly set.
- [ ] Hand-label **12+ golden pairs**, including 2+ hard negatives (clash-eval skill, `golden_pairs.TEMPLATE.jsonl`).
- [ ] Get **one sourced real story** for the 45-second opening.
- [ ] Prepare the demo video fallback slot (`docs/demo.mp4`, recorded on build day).

---

## 4. Build-day runbook

Times are relative, because the build window starts after the morning workshop. Push to git at each ✅.

### Phase 0: Kickoff (≈15 min)
1. Open the workspace. In chat, type `#steering` and confirm all the files are listed.
2. **Plan agent** (agent selector): *"Read #steering and #file:docs/SPEC_PROMPTS.md. List the top 5 risks to finishing a demoable build today and anything ambiguous in the specs."* Apply quick fixes to the steering or prompts.
3. Paste AWS credentials from Workshop Studio into `agent/.env`. Set **Supervised** mode. ✅

### Phase 1: Spec A, data-pipeline (Design-First)
- Prompt and checklist: `docs/SPEC_PROMPTS.md` §A. Run tasks one at a time. When `build_index.py` exists, the **data-reindex hook** starts working on its own. ✅

### Phase 2: Spec B, clash-agent (Requirements-First + Correctness)
- Switch the model to Sonnet for requirements and design, then back to Auto for tasks.
- Make the PBT tasks **required**. Screenshot any shrunk counterexample.
- Once `agent/eval.py` exists, use the **data-steward** agent to finalize the golden pairs, then iterate on `agent/prompts/clash_system.md`. The **prompt-eval hook** logs every iteration to `eval-history.csv`. That accuracy curve is a pitch asset.
- Use `atlas11-data` MCP lookups (`search_projects`, `get_project`) while labelling and debugging verdicts.
- Switch to **Autopilot** once the first three tasks are green. ✅

### Phase 3: Spec C, planner-dashboard + Spec D, gap-finder
- Spec C as Requirements-First (Autopilot is fine; the frontend-design steering guides the look).
- Spec D as a **Quick Spec**.
- The **schema-contract-sync** hook keeps `frontend/src/types/api.ts` aligned.
- Ask Kiro to run the flow with **Playwright MCP** at 1366×768 and save screenshots. ✅

### Phase 4: Bugfix spec
- Take the first real defect (an eval regression, a property failure or a demo-flow bug) and create a **Bugfix spec**. ✅

### Phase 5: Demo hardening (stop adding features at the halfway mark of the remaining time)
1. Generate `data/demo_cache/` by running the scripted scenario live once with `DEMO_MODE=record` (ask Kiro to add this mode if it's missing).
2. `/demo-readiness`: fix only what blocks the demo.
3. **Subagent:** *"Run the judge-simulator agent as a subagent on this repo."* Fix the "one thing".
4. `/impact-brief` (skill) → `docs/impact.md`. Then `/pitch-evidence` → `docs/kiro-usage.md` + a 45-second script.
5. `/sync-docs`. Screen-record the demo as `docs/demo.mp4`.
6. `/demo-rehearsal` (skill). Rehearse twice with a stopwatch. Tag the commit `demo-ready`. ✅

---

## 5. Pitch: 5 minutes + 2 minutes of Q&A

| Time | Content | Scores on |
|---|---|---|
| 0:00 | Real city, several funders, one high-need district left out (sourced) | Pres, SDG |
| 0:45 | "SDG 11.c lost its only indicator in 2020. Nobody tracks it. Atlas11 does." | SDG, Innov |
| 1:15 | **Live demo:** proposal → streaming agent trace → OVERLAPPING (co-finance) + COMPLEMENTARY look-alike → memo → approve → gap map flies to the redirect district | Innov, Tech |
| 4:15 | **Kiro slide:** EARS → property tests that caught a real bug; the eval hook's accuracy curve; steering encodes SDG 11 rules + the human-approval guardrail; custom MCP, Powers, skills, subagent judge | Tech |
| 4:45 | Scale: any country in the World Bank API or IATI; users are city planning offices and MDB country teams | SDG |

Q&A answers are in `.kiro/skills/demo-rehearsal/SKILL.md`. Refresh AWS credentials 10 minutes before presenting, and keep `DEMO_MODE=cached` and the video ready.

---

## 6. Risks and mitigations

| Risk | Mitigation already in the pack |
|---|---|
| Workshop AWS credentials expire mid-build or mid-demo | `aws-credentials.md` steering (hot reload, 503 banner), `aws-expiry-watch` hook, `DEMO_MODE=cached`, video |
| Hook or agent file format differs on the event's Kiro version | Verify step in §3; ask Kiro to recreate them from these definitions |
| Agent labels look-alike projects as duplicates | Deterministic `check_overlap` tool, taxonomy validator, properties, golden hard negatives, eval hook |
| Data looks made up | `data-honesty.md` (auto), provenance columns, seeded badges, snapshot date |
| Credits run out | Sequential accounts + `/handoff`, model-choice rules, command hooks, 12% reserve |
| Scope creep | Steering non-goals; stop features at the halfway mark of the remaining time; `judge-simulator` "fix one thing" |
| Venue Wi-Fi or Bedrock latency | Local embeddings fallback, cached mode, 20-second timeouts, offline-capable app |
