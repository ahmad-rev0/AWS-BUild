---
inclusion: fileMatch
fileMatchPattern: ["frontend/**"]
---
# Frontend design direction

## Feel
A calm, credible civic-tech tool, like a planning office's control room rather than a startup landing page. Dense but readable. The map is the hero.

## Layout (single page, three zones)
1. **Left panel (360px):** proposal form → after submission, the list of candidate verdicts.
2. **Centre:** Leaflet map with district polygons coloured by need score (sequential palette), project pins (shape by funder), the proposal pin pulsing, and lines from the proposal to candidates coloured by label.
3. **Right drawer (opens on demand):** coordination memo + "How the agent decided" (tool-call timeline) + Approve / Reject (only in Approver role).

## Label colours (use consistently everywhere)
- DUPLICATE: red `#C0392B`
- OVERLAPPING: amber `#D68910`
- COMPLEMENTARY: teal `#138D75`
- UNRELATED: grey `#7F8C8D`
Always pair the colour with a text label or icon. Never rely on colour alone.

## Components
- `VerdictCard`: label chip, project name, funder, amount, confidence bar, matching attributes as small tags, "why" expandable.
- `MemoPanel`: recommendation headline, summary, approve or reject buttons, audit link.
- `AgentTrace`: vertical timeline of tool calls with durations.
- `GapCallout`: banner when a redirect district exists, with a "Show on map" button that flies to it.
- `SeededBadge`: shown on any `source=seeded` record.

## Interaction
- Show a skeleton and a streaming status ("Searching 312 projects… Checking overlap… Drafting memo…") while the agent runs. Never a blank spinner.
- Role toggle (Planner / Approver) in the header.
- Everything must be operable at 1366×768. That's the likely projector resolution, so test at that size.

## Typography
- Inter, or the system UI font stack. 14px base, 12px for dense tables, tabular numbers for money.
- Format money as `US$240M`.
