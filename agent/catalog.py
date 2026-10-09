"""Compare a proposal with the local World Bank Projects API snapshot.

The rows in data/processed/projects.csv were fetched from
https://search.worldbank.org/api/v2/projects for Pakistan and Bangladesh.
This module does not invent coordinates, districts, or funding outcomes.
"""

from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path

from decimal import Decimal

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
PROJECTS_PATH = ROOT / "data" / "processed" / "projects.csv"
PROJECTS_API = "https://search.worldbank.org/api/v2/projects"

CITY_ALIASES = {
    "chattogram": "chittagong",
    "chittagong": "chittagong",
}

STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "project", "projects",
    "urban", "development", "government", "national", "province", "provincial",
    "additional", "financing", "support", "improvement", "services", "management",
    "through", "into", "their", "will", "been", "have", "which", "where", "under",
    "about", "after", "before", "between", "within", "using", "used", "also",
    "than", "then", "such", "other", "more", "most", "some", "only", "over",
    "area", "areas", "city", "cities", "local", "public", "sector", "program",
    "programme", "including", "include", "based", "phase", "second", "first",
    "third", "fourth", "component", "components", "total", "million", "billion",
    "world", "bank", "islamic", "republic", "peoples", "people", "bangladesh",
    "pakistan", "dhaka", "karachi", "lahore", "chittagong", "chattogram",
}


class CatalogProject(BaseModel):
    project_id: str
    name: str
    funder: str
    country: str
    city: str | None = None
    sector: str
    amount_usd: str
    status: str | None = None
    source: str
    source_url: str | None = None
    description: str


class CatalogCity(BaseModel):
    city: str
    country: str
    project_count: int


class CatalogCountry(BaseModel):
    country: str
    project_count: int


class CatalogSummary(BaseModel):
    source: str = "worldbank_api"
    projects_api: str = PROJECTS_API
    project_count: int
    projects_without_city: int
    countries: list[CatalogCountry]
    cities: list[CatalogCity]


class CatalogCompareRequest(BaseModel):
    title: str = Field(min_length=3)
    description: str = ""
    country: str | None = None
    city: str | None = None
    sector: str = ""


class CatalogMatch(BaseModel):
    project: CatalogProject
    label: str
    score: float
    shared_terms: list[str]
    same_city: bool
    explanation: str


class CatalogCompareResponse(BaseModel):
    matches: list[CatalogMatch]
    note: str


class CatalogUnavailableError(FileNotFoundError):
    pass


class CatalogCommitRequest(BaseModel):
    country: str = Field(min_length=1)
    city: str = Field(min_length=1)
    title: str = Field(min_length=3)
    amount_usd: Decimal = Field(ge=0)
    project_ids: list[str] = Field(default_factory=list)


class CatalogCommitment(BaseModel):
    commitment_id: str
    country: str
    city: str
    title: str
    amount_usd: str
    project_ids: list[str]
    created_at: str
    projects: list[CatalogProject]


def named_city(country: str, city: str) -> CatalogCity:
    """Return the World Bank city spelling for a country and city the records actually name."""
    wanted_country = _clean(country).lower()
    wanted_city = _place_key(city)
    for item in summary().cities:
        if item.country.lower() == wanted_country and _place_key(item.city) == wanted_city:
            return item
    raise ValueError("Choose a city named in the World Bank project records.")


def projects_by_ids(project_ids: list[str]) -> list[CatalogProject]:
    """Keep only project ids that exist in the World Bank snapshot, in request order."""
    index = {project.project_id: project for project in load_projects()}
    found: list[CatalogProject] = []
    seen: set[str] = set()
    for project_id in project_ids:
        project = index.get(project_id)
        if project is None or project.project_id in seen:
            continue
        seen.add(project.project_id)
        found.append(project)
    return found


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _excerpt(value: str, limit: int = 320) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _place_key(city: str | None) -> str:
    key = _clean(city).lower()
    return CITY_ALIASES.get(key, key)


def _tokens(*parts: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", " ".join(parts).lower())
    return {word for word in words if len(word) > 3 and word not in STOPWORDS}


def _as_project(row: dict[str, str]) -> CatalogProject:
    city = _clean(row.get("city"))
    return CatalogProject(
        project_id=_clean(row.get("project_id")),
        name=_clean(row.get("name")) or "Untitled World Bank project",
        funder=_clean(row.get("funder")) or "World Bank",
        country=_clean(row.get("country")),
        city=city or None,
        sector=_clean(row.get("sector")) or "Sector not stated",
        amount_usd=_clean(row.get("amount_usd")),
        status=_clean(row.get("status")) or None,
        source=_clean(row.get("source")) or "worldbank_api",
        source_url=_clean(row.get("source_url")) or None,
        description=_excerpt(_clean(row.get("description"))),
    )


@lru_cache(maxsize=1)
def load_projects() -> tuple[CatalogProject, ...]:
    if not PROJECTS_PATH.exists():
        raise CatalogUnavailableError(f"World Bank snapshot not found at {PROJECTS_PATH}")
    projects: list[CatalogProject] = []
    with PROJECTS_PATH.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if _clean(row.get("source")) not in {"", "worldbank_api"}:
                continue
            if not _clean(row.get("project_id")):
                continue
            projects.append(_as_project(row))
    return tuple(projects)


def summary() -> CatalogSummary:
    projects = load_projects()
    countries: dict[str, int] = {}
    cities: dict[tuple[str, str], int] = {}
    unplaced = 0
    for project in projects:
        countries[project.country] = countries.get(project.country, 0) + 1
        if project.city:
            key = (project.country, project.city)
            cities[key] = cities.get(key, 0) + 1
        else:
            unplaced += 1
    return CatalogSummary(
        project_count=len(projects),
        projects_without_city=unplaced,
        countries=[
            CatalogCountry(country=country, project_count=count)
            for country, count in sorted(countries.items(), key=lambda item: (-item[1], item[0]))
        ],
        cities=[
            CatalogCity(country=country, city=city, project_count=count)
            for (country, city), count in sorted(cities.items(), key=lambda item: (-item[1], item[0][1]))
        ],
    )


def list_projects(
    country: str | None = None,
    city: str | None = None,
    unplaced: bool = False,
    limit: int = 12,
) -> list[CatalogProject]:
    wanted_country = _clean(country).lower()
    wanted_city = _place_key(city)
    rows: list[CatalogProject] = []
    for project in load_projects():
        if wanted_country and project.country.lower() != wanted_country:
            continue
        if unplaced:
            if project.city:
                continue
        elif wanted_city and _place_key(project.city) != wanted_city:
            continue
        rows.append(project)
        if len(rows) >= limit:
            break
    return rows


def compare_catalog(query: CatalogCompareRequest) -> CatalogCompareResponse:
    query_tokens = _tokens(query.title, query.description, query.sector)
    if len(query_tokens) < 2:
        raise ValueError("Add a more specific title or description so the catalog can match real project text.")
    wanted_country = _clean(query.country).lower()
    wanted_city = _place_key(query.city)
    matches: list[CatalogMatch] = []
    for project in load_projects():
        if wanted_country and project.country.lower() != wanted_country:
            continue
        shared = sorted(query_tokens & _tokens(project.name, project.description, project.sector))
        if len(shared) < 2:
            continue
        same_city = bool(wanted_city and project.city and _place_key(project.city) == wanted_city)
        score = min(0.95, round(len(shared) / 6 + (0.28 if same_city else 0), 2))
        if same_city:
            place = f"Both name {project.city}."
            label = "OVERLAPPING"
        elif project.city and wanted_city:
            place = f"This record names {project.city}, not {query.city}."
            label = "COMPLEMENTARY"
        elif project.city:
            place = f"This record names {project.city}. The proposal did not name a city."
            label = "COMPLEMENTARY"
        else:
            place = "This record does not name a city, so it stays off the map."
            label = "COMPLEMENTARY"
        terms = ", ".join(shared[:6])
        matches.append(
            CatalogMatch(
                project=project,
                label=label,
                score=score,
                shared_terms=shared[:8],
                same_city=same_city,
                explanation=(
                    f"{place} Shared words in the World Bank title or description: {terms}. "
                    f"Record {project.project_id}."
                ),
            )
        )
    matches.sort(key=lambda item: (item.same_city, item.score, item.project.project_id), reverse=True)
    return CatalogCompareResponse(
        matches=matches[:5],
        note=(
            "Text and city match against the local World Bank Projects API snapshot "
            "for Pakistan and Bangladesh. A match is not a funding decision, and "
            "records without a city are not given a map location."
        ),
    )
