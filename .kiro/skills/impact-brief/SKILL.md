---
name: impact-brief
description: Produce honest, computed impact numbers and SDG 11 pitch copy for Atlas11 from the project dataset and gap analysis. Use when writing the pitch, README impact section, slide numbers, or answering "what is the impact / how does it scale" questions.
metadata:
  project: atlas11
---
# Impact brief

## Steps
1. Run the stats script over the current data:
   ```bash
   python .kiro/skills/impact-brief/scripts/impact_stats.py
   ```
   It prints Markdown: number of urban projects and funders covered, total commitments, projects per city, the share of projects with no city or district tagged (a data-gap finding in itself), and, if `data/geo/need_scores.csv` exists, the gap districts.
2. Read `.kiro/evidence/eval-history.csv` for the latest agent accuracy and hard-negative accuracy.
3. Write `docs/impact.md` with three short sections:
   - **Specific need (SDG 11):** 11.c has no indicator since 2020, and the gap districts found in our data.
   - **What Atlas11 changes:** appraisal effort saved per avoided overlap (explain qualitatively unless a cited figure exists), and money surfaced for redirect (computed).
   - **How it scales:** the same pipeline works for any country in the World Bank API or IATI (state the counts the APIs report; don't estimate).
4. Every number carries its source: "computed from projects.csv (n=…)" or a cited URL. Follow the data-honesty steering.

## Pitch copy rules
- Lead with one concrete city and one district, not global trillions.
- The finance gap is context, not the claim. The claim is coordination and visibility.
- Don't claim that duplication is the dominant problem. Research on aid fragmentation is mixed. Lean on gaps and transaction costs.
