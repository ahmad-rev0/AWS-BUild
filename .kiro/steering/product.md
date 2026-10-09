---
inclusion: always
---
# Product: Atlas11

> Working name. Rename with one find-and-replace across the repo if the team picks another.

## One-line pitch
Atlas11 shows city planners and development-finance officers **where urban development money is going, where it should be going, and who is doubling up**. An AI agent reviews every new urban project proposal against existing funded projects. Then a human approves its recommendation.

## The problem
- Several lenders and agencies (World Bank, ADB, AIIB, bilateral donors, national ministries) fund urban projects in the same cities, each with its own pipeline.
- Overlapping proposals waste appraisal effort. High-need districts with no funded project go unnoticed.
- SDG target **11.c** (financial and technical assistance to least developed countries for sustainable, resilient buildings) lost its only indicator, 11.c.1, in the UN's 2020 indicator review. Nobody systematically tracks it. Atlas11 provides that tracking.
- The concept comes from the "Unified Donor Coordination" pillar of the D.U.N.E. framework (ECOSOC position paper, NTUMUN 2026). There it is an "AI-enabled clash recognition system" with sign-off by senior officers.

## SDG alignment (SDG 11: Sustainable Cities and Communities)
| Target | How Atlas11 serves it |
|---|---|
| 11.c | Tracks and coordinates financial assistance for sustainable, resilient urban infrastructure |
| 11.a / 11.b | Integrated planning across agencies and levels of government; resilience-focused allocation |
| 11.3 | Transparent, participatory planning, since decisions and rationale are visible |
| 11.1, 11.2, 11.5, 11.6 | Taxonomy of the projects we classify (housing, transport, disaster resilience, water/waste) |

## Users
- **Primary:** a city or provincial planning officer, or a donor programme officer, reviewing a new proposal.
- **Secondary:** an approver (a senior officer) who signs off on coordination recommendations.

## Core features, in priority order
1. **Proposal intake:** submit a new urban project (title, description, city or district, sector, budget, dates).
2. **Clash review (agentic):** retrieve similar funded projects with vector search, filter by geography, time and sector, then have the agent classify each candidate as `DUPLICATE | OVERLAPPING | COMPLEMENTARY | UNRELATED` with reasons and a confidence score.
3. **Coordination memo:** the agent drafts a short memo (recommend merge, co-finance, proceed or redirect).
4. **Human approval:** an approver accepts or rejects the recommendation. Nothing changes status without approval.
5. **Gap map:** a district map of funded projects against a need score, highlighting high-need districts with no funding.
6. **Audit trail:** every agent decision, tool call and human approval is logged and viewable.

## Non-goals (for the hackathon)
- No real money movement, payments or integration with any bank system.
- No user accounts or authentication beyond a simple role toggle (Planner / Approver).
- No live data scraping during the demo. Data is pre-fetched and loaded from local files.

## Demo story (5 minutes)
1. Problem hook (45s): one real city with several funders and one high-need district left out.
2. Gap in SDG measurement (30s): 11.c has no indicator, and Atlas11 provides one.
3. Live demo (2.5 min): submit proposal → agent finds an OVERLAPPING project (recommend co-finance) and a COMPLEMENTARY one that only *sounds* similar → memo → approve → gap map shows the redirect target.
4. How Kiro built it (45s): steering, specs with EARS and property tests, hooks that regression-test the agent, MCP and Powers, skills, custom agents.
5. Impact and scale (30s): works for any city with open project data (World Bank API, IATI).

## Judging criteria (25 points each). Every feature must serve at least one.
- **Innovation:** an agent that reasons about overlap rather than just matching text, plus gap detection.
- **Technical implementation (Kiro):** visible, explained use of every Kiro feature.
- **SDG values and impact:** a specific need (11.c tracking, under-funded districts) and scalability.
- **Presentation:** a clear story, a working demo and confident Q&A.
