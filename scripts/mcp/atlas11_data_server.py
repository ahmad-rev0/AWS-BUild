#!/usr/bin/env python3
"""Custom MCP server exposing the Atlas11 project dataset to Kiro while you build.

Lets Kiro (and the data-steward agent) look up real projects while labelling eval pairs,
writing seeded proposals or debugging verdicts, without pasting CSVs into chat.
Run by Kiro via .kiro/settings/mcp.json:  uv run --with "mcp<2" python scripts/mcp/atlas11_data_server.py
"""
import csv
from collections import Counter
from pathlib import Path

from mcp.server.fastmcp import FastMCP

ROOT = Path(__file__).resolve().parents[2]
FILES = [ROOT / "data/processed/projects.csv", ROOT / "data/processed/seeded_projects.csv"]
mcp = FastMCP("atlas11-data")


def _rows() -> list[dict]:
    out: list[dict] = []
    for f in FILES:
        if f.exists():
            out.extend(csv.DictReader(f.open(encoding="utf-8")))
    return out


@mcp.tool()
def search_projects(query: str, city: str = "", limit: int = 10) -> list[dict]:
    """Keyword search over Atlas11 projects (name, description, themes). Optional exact city filter.
    Returns id, name, funder, city, amount_usd, approval_date, source."""
    terms = [t.lower() for t in query.split() if t]
    scored = []
    for r in _rows():
        if city and r.get("city", "").lower() != city.lower():
            continue
        hay = " ".join([r.get("name", ""), r.get("description", ""), r.get("themes", "")]).lower()
        s = sum(hay.count(t) for t in terms)
        if s:
            scored.append((s, r))
    scored.sort(key=lambda x: -x[0])
    keys = ["project_id", "name", "funder", "city", "amount_usd", "approval_date", "source"]
    return [{k: r.get(k, "") for k in keys} for _, r in scored[:limit]]


@mcp.tool()
def get_project(project_id: str) -> dict:
    """Return the full record for one project ID, or an error message."""
    for r in _rows():
        if r.get("project_id") == project_id:
            return r
    return {"error": f"{project_id} not found"}


@mcp.tool()
def dataset_stats() -> dict:
    """Counts by source, funder and city, so you can check coverage quickly."""
    rows = _rows()
    return {
        "total": len(rows),
        "by_source": Counter(r.get("source", "") for r in rows),
        "by_funder": Counter(r.get("funder", "") for r in rows),
        "top_cities": Counter(r.get("city") or "(untagged)" for r in rows).most_common(15),
    }


if __name__ == "__main__":
    mcp.run()
