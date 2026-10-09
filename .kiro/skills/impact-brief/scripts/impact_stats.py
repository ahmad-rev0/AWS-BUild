#!/usr/bin/env python3
"""Print computed impact statistics (Markdown) from Atlas11 data files."""
import csv
from collections import Counter, defaultdict
from pathlib import Path

P = Path("data/processed/projects.csv")
N = Path("data/geo/need_scores.csv")
if not P.exists():
    raise SystemExit("data/processed/projects.csv not found. Run the worldbank-ingest skill first.")

rows = list(csv.DictReader(P.open(encoding="utf-8")))
urban = [r for r in rows if r.get("is_urban", "true") == "true"]


def amt(r):
    try:
        return float(r.get("amount_usd") or 0)
    except ValueError:
        return 0.0


total = sum(amt(r) for r in urban)
by_city = Counter(r["city"] or "(untagged)" for r in urban)
by_city_amt = defaultdict(float)
for r in urban:
    by_city_amt[r["city"] or "(untagged)"] += amt(r)
funders = Counter(r["funder"] for r in urban)
untagged = by_city["(untagged)"]

print(f"## Computed from {P} (n={len(urban)} urban projects)\n")
print(f"- Funders covered: {', '.join(f'{k} ({v})' for k, v in funders.most_common())}")
print(f"- Total commitments: US${total/1e9:.2f}B")
print(f"- Projects without a city tag: {untagged} ({untagged/max(len(urban),1):.0%}). "
      "This is a visibility gap in itself.")
print("\n| City | Projects | Commitments |\n|---|---|---|")
for c, n in by_city.most_common(12):
    print(f"| {c} | {n} | US${by_city_amt[c]/1e6:,.0f}M |")

if N.exists():
    needs = list(csv.DictReader(N.open(encoding="utf-8")))
    gaps = [d for d in needs if float(d.get("need_score", 0)) >= 0.6
            and float(d.get("funding_per_capita", 0) or 0) <= sorted(
                float(x.get("funding_per_capita", 0) or 0) for x in needs)[len(needs) // 4]]
    print(f"\n## Gap districts (need_score ≥ 0.6, funding per capita in bottom quartile): {len(gaps)}")
    for d in gaps:
        print(f"- {d.get('district_name', d.get('district_id'))} (need {float(d['need_score']):.2f}, "
              f"quality: {d.get('indicator_quality', 'unknown')})")
else:
    print("\n(no data/geo/need_scores.csv yet, so gap districts weren't computed)")
