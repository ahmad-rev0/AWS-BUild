#!/usr/bin/env python3
"""Fetch World Bank projects for given countries and normalize the urban ones.

Standard library only. Usage:
    python fetch_worldbank.py --countries PK BD --out data
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://search.worldbank.org/api/v2/projects"
PAGE = 200
URBAN_THEME_HINTS = ("urban", "municipal", "city", "housing", "transport", "water", "sanitation",
                     "drainage", "flood", "resilien", "solid waste", "land administration")
URBAN_NAME_HINTS = re.compile(
    r"\b(urban|city|cities|municipal|metro|brt|bus rapid|transit|mobility|housing|slum|"
    r"water (supply|and sewerage)|sewerage|sanitation|drainage|flood|solid waste|resilien\w*)\b",
    re.I)
# Extend per country. A match only fills the `city` column (never guessed beyond these names).
KNOWN_CITIES = {
    "PK": ["Karachi", "Lahore", "Islamabad", "Rawalpindi", "Peshawar", "Faisalabad", "Multan",
           "Quetta", "Hyderabad", "Gujranwala", "Sialkot"],
    "BD": ["Dhaka", "Chattogram", "Chittagong", "Khulna", "Rajshahi", "Sylhet", "Barishal",
           "Rangpur", "Mymensingh", "Gazipur", "Narayanganj"],
}


def fetch_country(cc: str, raw_dir: Path) -> list[dict]:
    projects: list[dict] = []
    offset = 0
    pages = []
    while True:
        qs = urllib.parse.urlencode({"format": "json", "countrycode_exact": cc,
                                     "rows": PAGE, "os": offset})
        req = urllib.request.Request(f"{API}?{qs}", headers={"User-Agent": "atlas11-hackathon"})
        with urllib.request.urlopen(req, timeout=60) as r:
            page = json.load(r)
        pages.append(page)
        batch = list((page.get("projects") or {}).values())
        projects.extend(batch)
        total = int(page.get("total", 0))
        offset += PAGE
        print(f"  {cc}: {len(projects)}/{total}", file=sys.stderr)
        if not batch or offset >= total:
            break
        time.sleep(0.5)
    (raw_dir / f"worldbank_{cc}.json").write_text(json.dumps(pages, indent=1))
    return projects


def _text(v) -> str:
    if v is None:
        return ""
    if isinstance(v, dict):
        return str(v.get("cdata") or v.get("Name") or v.get("name") or "")
    if isinstance(v, list):
        return "; ".join(filter(None, (_text(x) for x in v)))
    return str(v)


def _themes(p: dict) -> list[str]:
    names: list[str] = []

    def walk(node):
        if isinstance(node, list):
            for n in node:
                walk(n)
        elif isinstance(node, dict):
            if node.get("name"):
                names.append(node["name"])
            for k in ("theme2", "theme3"):
                walk(node.get(k))
    walk(p.get("theme_list"))
    return names


def _amount(v) -> str:
    s = re.sub(r"[^\d.]", "", _text(v))
    return s or ""


def normalize(p: dict, cc: str) -> dict:
    name = _text(p.get("project_name"))
    themes = _themes(p)
    agency = _text(p.get("impagency"))
    abstract = _text(p.get("project_abstract"))
    hay = " ".join([name, agency, " ".join(themes)])
    city = next((c for c in KNOWN_CITIES.get(cc, []) if re.search(rf"\b{c}\b", hay, re.I)), "")
    is_urban = bool(URBAN_NAME_HINTS.search(hay)) or any(
        h in t.lower() for t in themes for h in URBAN_THEME_HINTS)
    desc = abstract or f"{name}. Implementing agency: {agency}. Themes: {', '.join(themes[:8])}."
    return {
        "project_id": p.get("id", ""),
        "name": name,
        "funder": "World Bank",
        "country": _text(p.get("countryshortname")) or cc,
        "city": city,
        "district": "",
        "sector": _text(p.get("sector1")) or (themes[0] if themes else ""),
        "themes": "|".join(themes),
        "description": desc.strip(),
        "amount_usd": _amount(p.get("totalcommamt") or p.get("totalamt")),
        "approval_date": _text(p.get("boardapprovaldate"))[:10],
        "closing_date": _text(p.get("closingdate")),
        "status": _text(p.get("status")),
        "is_urban": str(is_urban).lower(),
        "source": "worldbank_api",
        "source_url": _text(p.get("url")),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--countries", nargs="+", default=["PK", "BD"])
    ap.add_argument("--out", default="data")
    ap.add_argument("--all", action="store_true", help="keep non-urban projects too")
    a = ap.parse_args()
    out = Path(a.out)
    (out / "raw").mkdir(parents=True, exist_ok=True)
    (out / "processed").mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for cc in a.countries:
        for p in fetch_country(cc.upper(), out / "raw"):
            r = normalize(p, cc.upper())
            if a.all or r["is_urban"] == "true":
                rows.append(r)
    if not rows:
        sys.exit("No rows fetched. Check network access to search.worldbank.org")
    path = out / "processed" / "projects.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with_city = sum(1 for r in rows if r["city"])
    with_abs = sum(1 for r in rows if not r["description"].startswith(r["name"] + ". Implementing"))
    print(f"Wrote {len(rows)} rows to {path} ({with_city} with city, {with_abs} with abstracts)")


if __name__ == "__main__":
    main()
