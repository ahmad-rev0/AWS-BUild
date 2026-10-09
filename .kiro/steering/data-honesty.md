---
inclusion: auto
name: data-honesty
description: Rules for data provenance, labelling seeded or illustrative data, and avoiding fabricated statistics. Use when creating, transforming, displaying or describing any dataset, metric, impact number or chart.
---
# Data honesty rules

Judges reward honesty and punish numbers that look made up. Follow these rules everywhere.

1. **Provenance on every record.** Each project row carries `source` (`worldbank_api`, `iati`, `seeded`) and `source_url` where one exists.
2. **Seeded data is labelled.** The demo's incoming proposal and any synthetic records have `source=seeded`, and the UI shows a visible "Seeded for demo" badge on them.
3. **Illustrative indicators are labelled.** If a district need indicator is estimated or illustrative, `need_scores.csv` has `indicator_quality = measured|estimated|illustrative`, and the map legend says so.
4. **Never invent statistics** for the UI, README or pitch copy. Every impact number must come from (a) computation over our data, shown with the query, or (b) a cited public source with URL. Otherwise write "TBD: needs source".
5. **Never invent real-world claims** about specific funders or projects (e.g. "Bank X duplicated Bank Y in 2023") unless a source URL is in the data.
6. Charts and the dashboard state the data snapshot date ("World Bank API, fetched 2026-10-XX").
