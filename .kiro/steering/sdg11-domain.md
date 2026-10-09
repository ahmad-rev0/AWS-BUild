---
inclusion: fileMatch
fileMatchPattern: ["agent/**", "data/**", "scripts/**", ".kiro/specs/**"]
---
# SDG 11 domain knowledge and clash taxonomy

## Clash classification: the core of the product
The agent classifies every (proposal, existing project) pair as exactly one of the following.

| Label | Definition | Typical recommendation |
|---|---|---|
| `DUPLICATE` | Same objective, same location (district or city), overlapping period, and substantially the same outputs. Funding both would pay twice for one result. | **Merge** or reject the newer proposal; refer to the approver |
| `OVERLAPPING` | Same location and period with partly shared outputs or beneficiaries (e.g. both build drainage in the same district, but one also does housing). | **Co-finance or coordinate**: shared procurement, split scope |
| `COMPLEMENTARY` | Similar sector or wording, but different location, corridor, phase or beneficiaries, so the two reinforce each other (e.g. BRT Red Line vs BRT Yellow Line). | **Proceed**; link the projects for joint monitoring |
| `UNRELATED` | Retrieved by similarity but no meaningful relationship. | Proceed |

### Decision rules (the agent must apply these in order)
1. **Geography first.** A different city means it cannot be `DUPLICATE` or `OVERLAPPING`. The same city but a different district is at most `OVERLAPPING`, and only if the beneficiaries are shared.
2. **Time second.** Implementation periods must overlap (allowing 12 months of slack) for `DUPLICATE` or `OVERLAPPING`.
3. **Outputs third.** Compare concrete outputs (km of pipe, number of housing units, BRT corridor name), not adjectives.
4. **High text similarity alone never justifies `DUPLICATE`.** The agent must cite at least two concrete matching attributes (location + output, or location + beneficiaries).
5. When evidence is insufficient, choose the *less severe* label and lower the confidence.

## Need score (gap map)
`need_score` per district, from 0 to 1, is a weighted combination of available indicators. Weights live in `data/geo/need_weights.json`:

#[[file:data/geo/need_weights.json]]

- Population density
- Share of population in informal settlements or slums (SDG indicator 11.1.1) where available
- Flood or disaster exposure (11.5)
- Public transport access (11.2.1) where available
A **gap** is a district with `need_score ≥ 0.6` and funded commitments per capita in the bottom quartile.

## SDG 11 target reference (use exact wording in UI tooltips)
- **11.1** Adequate, safe and affordable housing and basic services; upgrade slums
- **11.2** Safe, affordable, accessible and sustainable transport systems
- **11.3** Inclusive and sustainable urbanization and participatory planning
- **11.5** Reduce deaths and economic losses from disasters, including water-related disasters
- **11.6** Reduce the per-capita environmental impact of cities (air quality, waste)
- **11.a** Support positive links between urban, peri-urban and rural areas through national and regional development planning
- **11.b** Integrated policies for inclusion, resource efficiency, climate change and disaster resilience
- **11.c** Support least developed countries, including through financial and technical assistance, in building sustainable and resilient buildings utilizing local materials. *(Indicator 11.c.1 was deleted in the 2020 comprehensive review.)*

## Terminology
- Say "funder" (covers MDBs, bilateral donors and ministries), "proposal" (new) and "project" (existing, funded).
- MDB = multilateral development bank. ODA = official development assistance.
