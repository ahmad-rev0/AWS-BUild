---
name: demo-rehearsal
description: Rehearse and harden the 5-minute Atlas11 pitch and 2-minute Q&A, including the scripted demo path, timing, fallbacks and judge questions. Use when preparing for or rehearsing the final showcase, or when asked to "practise the pitch", "prepare Q&A" or "make the demo bulletproof".
metadata:
  project: atlas11
---
# Demo rehearsal

## 1. Scripted path (must match `scripts/demo_smoke.py`)
| Time | Screen | Spoken line (short) |
|---|---|---|
| 0:00–0:45 | Title, then map of the city | Problem: several funders, one city, one district left out |
| 0:45–1:15 | SDG 11 target card | "11.c lost its indicator in 2020. Nobody tracks it. We do." |
| 1:15–2:30 | Submit seeded proposal → agent trace streams | Agent searches, checks facts, classifies |
| 2:30–3:15 | Verdicts: OVERLAPPING + COMPLEMENTARY | "Similar words, different corridor, so not a clash. Text matching would get this wrong." |
| 3:15–3:45 | Memo → switch to Approver → Approve | Human in the loop, audit trail |
| 3:45–4:15 | Gap callout → map flies to district | Redirect to the high-need district |
| 4:15–5:00 | Kiro slide (from docs/kiro-usage.md) + impact | How Kiro built it, and how it scales |

## 2. Fallback ladder (decide before going on stage)
1. Live Bedrock → 2. `DEMO_MODE=cached` (identical UI) → 3. Screen-recorded video in `docs/demo.mp4`.
Refresh AWS credentials **10 minutes before** presenting, because they expire after an hour.

## 3. Q&A drill
Invoke the `judge-simulator` custom agent (`.kiro/agents/judge-simulator.md`) as a subagent: "Act as the 4 judges; ask 8 hard questions on our repo." Then rehearse answers of 20 seconds or less. Must-prepare questions:
- Isn't this IATI or AidData? (Those are data sources; we reason over them and act on them.)
- How do you know the agent is right? (Golden-pair eval + property tests + a hook on every prompt change; quote accuracy.)
- What if it wrongly flags a duplicate? (Human approval; DUPLICATE needs at least 2 concrete matching attributes; less severe label when unsure.)
- Is the data real? (World Bank API, snapshot date; seeded items are badged.)
- How does it scale or make money? (Any city with open data; city planning offices and MDB country teams; SaaS or open-source + support.)
- Why Kiro specifically? (Specs → PBT; steering encodes domain rules; hooks guard quality.)

## 4. Timing
Rehearse with a stopwatch at least twice. If you're over 5:00, cut the impact section first, never the demo.
