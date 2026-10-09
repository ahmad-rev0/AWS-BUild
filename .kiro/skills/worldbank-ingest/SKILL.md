---
name: worldbank-ingest
description: Fetch and normalize real urban development projects from the World Bank Projects API (and optionally IATI) into data/processed/projects.csv for Atlas11. Use when asked to fetch, refresh, extend or add a country or city to the project dataset, or when projects.csv is missing.
compatibility: Python 3.11+, network access to search.worldbank.org. No third-party packages needed.
metadata:
  project: atlas11
  version: "1.0"
---
# World Bank / IATI ingest

## When to use
- `data/processed/projects.csv` is missing or stale
- The team wants to add a country or city
- Before the hackathon, as **pre-event data preparation** (data only, no app code)

## Steps
1. Run the fetcher for each target country (ISO-2 codes). Default focus is Pakistan (PK) and Bangladesh (BD):
   ```bash
   python .kiro/skills/worldbank-ingest/scripts/fetch_worldbank.py --countries PK BD --out data
   ```
   This writes `data/raw/worldbank_<CC>.json` (untouched API pages) and `data/processed/projects.csv`.
2. Open `data/processed/projects.csv` and check that:
   - rows have `source=worldbank_api` and a `source_url`
   - `is_urban` is true for at least 50 projects per country (urban filter = theme names + keyword match)
   - `city` is filled where the project name or implementing agency names a city. If it's blank, it's fine to leave it blank. **Don't guess.**
3. If the API omits abstracts, the `description` column falls back to the project name + implementing agency + themes. Tell the user this, because it affects embedding quality.
4. Optional, IATI: the IATI Datastore API needs a free subscription key (`IATI_KEY`). If the key is present, run with `--iati`. Otherwise skip it and say so.
5. Rebuild the vector index (the data-change hook normally does this automatically):
   `python scripts/build_index.py`

## Normalized schema (`projects.csv`)
`project_id, name, funder, country, city, district, sector, themes, description, amount_usd, approval_date, closing_date, status, is_urban, source, source_url`

## Rules
- Never hand-edit `data/raw/`.
- Seeded or demo records go in `data/processed/seeded_projects.csv` with `source=seeded`. Never mix them into the raw-derived file.
- Follow the data-honesty steering.
