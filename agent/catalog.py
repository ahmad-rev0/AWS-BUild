"""Compare a proposal with the local World Bank Projects API snapshot.

The rows in data/processed/projects.csv were fetched from
https://search.worldbank.org/api/v2/projects for Pakistan and Bangladesh.
This module does not invent coordinates, districts, or funding outcomes.
"""

from __future__ import annotations

import csv
import json
import os
import re
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path

from decimal import Decimal, InvalidOperation, ROUND_DOWN

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
    "government", "national", "province", "provincial", "financing", "through",
    "into", "their", "will", "been", "have", "which", "where", "under", "about",
    "after", "before", "between", "within", "using", "used", "also", "than",
    "then", "such", "other", "more", "most", "some", "only", "over", "area",
    "areas", "city", "cities", "local", "including", "include", "based", "phase",
    "second", "first", "third", "fourth", "total", "million", "billion", "world",
    "bank", "islamic", "republic", "peoples", "people", "bangladesh", "pakistan",
    "dhaka", "karachi", "lahore", "chittagong", "chattogram",
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


class AreaOption(BaseModel):
    country: str
    city: str
    project_count: int
    worldbank_usd: str
    relevance: float
    nearest_project_id: str | None = None
    nearest_project_name: str | None = None
    nearest_source_url: str | None = None
    recommended: bool
    reason: str


class CatalogRecommendation(BaseModel):
    country: str
    recommended_city: str
    call: str
    summary: str
    note: str
    areas: list[AreaOption]
    model_id: str = ""


class CatalogUnavailableError(FileNotFoundError):
    pass


class CatalogCommitRequest(BaseModel):
    country: str = Field(min_length=1)
    city: str = Field(min_length=1)
    title: str = Field(min_length=3)
    amount_usd: Decimal = Field(ge=0)
    project_ids: list[str] = Field(default_factory=list)
    recommended_city: str | None = None
    human_choice: str = "unreviewed"
    decision_note: str = ""


class ProjectImpact(BaseModel):
    project_id: str
    name: str
    source_url: str | None = None
    label: str
    worldbank_amount_usd: str
    added_usd: str
    combined_usd: str
    connection: str


class FundingImpact(BaseModel):
    worldbank_in_city_usd: str
    added_usd: str
    after_usd: str
    lines: list[ProjectImpact]


class CatalogCommitment(BaseModel):
    commitment_id: str
    country: str
    city: str
    title: str
    amount_usd: str
    project_ids: list[str]
    created_at: str
    projects: list[CatalogProject]
    impact: FundingImpact
    recommended_city: str | None = None
    human_choice: str = "unreviewed"
    decision_note: str = ""


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


def _as_match(
    project: CatalogProject,
    query: CatalogCompareRequest,
    score: float,
    query_tokens: set[str],
) -> CatalogMatch:
    wanted_city = _place_key(query.city)
    same_city = bool(wanted_city and project.city and _place_key(project.city) == wanted_city)
    shared = sorted(query_tokens & _tokens(project.name, project.description, project.sector))
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
    word_note = f" Shared words: {terms}." if terms else ""
    return CatalogMatch(
        project=project,
        label=label,
        score=min(0.95, round(score, 2)),
        shared_terms=shared[:8],
        same_city=same_city,
        explanation=f"Chroma similarity {score:.0%}. {place}{word_note} Record {project.project_id}.",
    )


def _chroma_candidates(query: CatalogCompareRequest) -> list[tuple[CatalogProject, float]]:
    text = " ".join(part for part in (query.title, query.description, query.sector) if part).strip()
    from agent.retrieval import search

    found = search(text, k=8)
    by_id = {project.project_id: project for project in load_projects()}
    wanted_country = _clean(query.country).lower()
    chosen: list[tuple[CatalogProject, float]] = []
    for candidate in found:
        project = by_id.get(candidate.project_id)
        if project is None:
            continue
        if wanted_country and project.country.lower() != wanted_country:
            continue
        chosen.append((project, float(candidate.score)))
    return chosen


def compare_catalog(query: CatalogCompareRequest, *, limit: int | None = 5) -> CatalogCompareResponse:
    query_tokens = _tokens(query.title, query.description, query.sector)
    if len(query_tokens) < 2 and len(_tokens(query.title, query.description)) < 2:
        raise ValueError("Add a more specific title or description so the catalog can match real project text.")
    try:
        chroma_hits = _chroma_candidates(query)
    except Exception:
        chroma_hits = []
    if chroma_hits:
        matches = [_as_match(project, query, score, query_tokens) for project, score in chroma_hits]
        return CatalogCompareResponse(
            matches=matches if limit is None else matches[:limit],
            note=(
                "Nearest projects from the local Chroma index of the World Bank snapshot. "
                "Same city is overlapping and receives co-finance. A different or missing city is complementary."
            ),
        )
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
        matches=matches if limit is None else matches[:limit],
        note=(
            "Text and city match against the local World Bank Projects API snapshot "
            "for Pakistan and Bangladesh. A match is not a funding decision, and "
            "records without a city are not given a map location."
        ),
    )


# A city stays in the "close enough" set when its best project is within this
# similarity of the nearest project. Below the floor, thinner coverage is not used.
_RELEVANCE_FLOOR = 0.45
_CLOSE_BAND = 0.08


def pick_funding_area(options: list[tuple[str, float, Decimal]]) -> tuple[str, str]:
    """Choose a city from (city, relevance, existing World Bank USD).

    When two cities are close to the proposal, the one with less money already
    on record is chosen. A weak match does not get that thinner-coverage boost.
    """
    if not options:
        raise ValueError("No named city is available for this country.")
    ranked = sorted(options, key=lambda item: (-item[1], item[2], item[0]))
    best_city, best_score, _best_usd = ranked[0]
    if best_score < _RELEVANCE_FLOOR:
        return best_city, "no_close_match"
    close = [item for item in ranked if item[1] >= best_score - _CLOSE_BAND]
    chosen = min(close, key=lambda item: (item[2], -item[1], item[0]))
    richest = max(close, key=lambda item: (item[2], item[0]))
    if chosen[2] < richest[2]:
        return chosen[0], "thinner_coverage"
    return chosen[0], "closest_work"


def _compact_money(value: Decimal) -> str:
    amount = abs(value)
    if amount >= Decimal(1_000_000_000):
        return f"US${(value / Decimal(1_000_000_000)):.1f}B"
    if amount >= Decimal(1_000_000):
        return f"US${(value / Decimal(1_000_000)):.0f}M"
    return f"US${value.quantize(Decimal('1')):,.0f}"


def _city_rollups(country: str) -> dict[str, dict[str, object]]:
    wanted = _clean(country).lower()
    rollups: dict[str, dict[str, object]] = {}
    for project in load_projects():
        if project.country.lower() != wanted or not project.city:
            continue
        key = _place_key(project.city)
        bucket = rollups.get(key)
        if bucket is None:
            bucket = {
                "key": key,
                "city": project.city,
                "country": project.country,
                "count": 0,
                "usd": Decimal(0),
                "best_score": 0.0,
                "best_project": None,
            }
            rollups[key] = bucket
        bucket["count"] = int(bucket["count"]) + 1
        bucket["usd"] = _decimal(str(bucket["usd"])) + _decimal(project.amount_usd)
        if key == "chittagong":
            bucket["city"] = "Chittagong"
    return rollups


def _apply_chroma(query: CatalogCompareRequest, rollups: dict[str, dict[str, object]]) -> bool:
    text = " ".join(part for part in (query.title, query.description, query.sector) if part).strip()
    from agent.retrieval import search

    found = search(text, k=100)
    by_id = {project.project_id: project for project in load_projects()}
    wanted = _clean(query.country).lower()
    hit = False
    for candidate in found:
        project = by_id.get(candidate.project_id)
        if project is None or not project.city or project.country.lower() != wanted:
            continue
        bucket = rollups.get(_place_key(project.city))
        if bucket is None:
            continue
        score = float(candidate.score)
        hit = True
        if score > float(bucket["best_score"]):
            bucket["best_score"] = score
            bucket["best_project"] = project
    return hit


def _apply_words(query: CatalogCompareRequest, rollups: dict[str, dict[str, object]]) -> None:
    query_tokens = _tokens(query.title, query.description, query.sector)
    wanted = _clean(query.country).lower()
    for project in load_projects():
        if project.country.lower() != wanted or not project.city:
            continue
        shared = query_tokens & _tokens(project.name, project.description, project.sector)
        if len(shared) < 2:
            continue
        bucket = rollups.get(_place_key(project.city))
        if bucket is None:
            continue
        score = min(0.95, len(shared) / 6)
        if score > float(bucket["best_score"]):
            bucket["best_score"] = score
            bucket["best_project"] = project


_CHAT_MODEL_PREFERENCE = ("qwen2.5:3b", "gemma4:12b", "deepseek-r1:8b", "gemma4:e4b")


def parse_chat_choice(text: str, cities: list[str]) -> tuple[str, str, str] | None:
    """Read a city, call, and reason from a chat model's JSON. Unknown cities are rejected."""
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    raw_city = str(payload.get("city") or "").strip()
    call = str(payload.get("call") or "").strip()
    reason = " ".join(str(payload.get("reason") or "").split())
    by_key = {_place_key(city): city for city in cities}
    city = by_key.get(_place_key(raw_city))
    if city is None or call not in {"thinner_coverage", "closest_work", "no_close_match"}:
        return None
    if len(reason) < 8:
        return None
    return city, call, reason[:320]


def _ollama_models() -> list[str]:
    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    with urllib.request.urlopen(f"{host}/api/tags", timeout=3) as response:
        payload = json.loads(response.read().decode())
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return []
    names: list[str] = []
    for item in models:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            names.append(item["name"])
    return names


def _select_chat_model(installed: list[str]) -> str | None:
    requested = os.getenv("ATLAS11_CHAT_MODEL", "").strip()
    candidates = [requested, *_CHAT_MODEL_PREFERENCE] if requested else list(_CHAT_MODEL_PREFERENCE)
    for candidate in candidates:
        if not candidate:
            continue
        for name in installed:
            if name == candidate or name == f"{candidate}:latest":
                return name
    return None


def _ask_local_chat(
    query: CatalogCompareRequest,
    options: list[tuple[str, float, Decimal]],
) -> tuple[str, str, str, str] | None:
    """Ask a local Ollama chat model to choose a city. Returns None if it cannot."""
    try:
        installed = _ollama_models()
    except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return None
    model = _select_chat_model(installed)
    if model is None:
        return None
    lines = [
        f"- {city}: similarity {score:.0%}, World Bank on record {_compact_money(usd)}"
        for city, score, usd in sorted(options, key=lambda item: (-item[1], item[0]))
    ]
    prompt = (
        "Choose one city for this proposal. Use only the cities and figures below. "
        "Do not invent amounts, projects, or cities.\n\n"
        f"Proposal title: {query.title}\n"
        f"What it would fund: {query.description}\n"
        f"Sector: {query.sector}\n"
        f"Country: {query.country}\n\n"
        "Cities named in the World Bank snapshot:\n"
        + "\n".join(lines)
        + "\n\nRules:\n"
        "- If the best similarity is under 45%, choose that nearest city and set call to no_close_match.\n"
        "- If another city is within 8 percentage points of the best similarity and has less World Bank money on record, choose that thinner city and set call to thinner_coverage.\n"
        "- Otherwise choose the highest similarity and set call to closest_work.\n"
        'Reply with JSON only: {"city":"...","call":"thinner_coverage|closest_work|no_close_match","reason":"one sentence using only the figures above"}'
    )
    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    body: dict[str, object] = {
        "model": model,
        "stream": False,
        "format": "json",
        "messages": [
            {"role": "system", "content": "You answer with one JSON object and no other text."},
            {"role": "user", "content": prompt},
        ],
        "think": False,
        "options": {"temperature": 0, "num_predict": 160},
    }
    request = urllib.request.Request(
        f"{host}/api/chat",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = json.loads(response.read().decode())
    except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return None
    message = payload.get("message") if isinstance(payload, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        return None
    parsed = parse_chat_choice(content, [city for city, _score, _usd in options])
    if parsed is None:
        return None
    city, call, reason = parsed
    return city, call, reason, model


def recommend_catalog(query: CatalogCompareRequest) -> CatalogRecommendation:
    """Rank named cities for this proposal and leave the funding choice open."""
    if not _clean(query.country):
        raise ValueError("Choose a country first.")
    query_tokens = _tokens(query.title, query.description, query.sector)
    if len(query_tokens) < 2 and len(_tokens(query.title, query.description)) < 2:
        raise ValueError("Add a more specific title or description so the catalog can match real project text.")
    rollups = _city_rollups(query.country)
    if not rollups:
        raise ValueError("This country has no World Bank project that names a city.")
    used_chroma = False
    try:
        used_chroma = _apply_chroma(query, rollups)
    except Exception:
        used_chroma = False
    if not used_chroma:
        _apply_words(query, rollups)
    options = [
        (str(bucket["city"]), float(bucket["best_score"]), _decimal(str(bucket["usd"])))
        for bucket in rollups.values()
    ]
    chat = _ask_local_chat(query, options)
    if chat is None:
        chosen_city, call = pick_funding_area(options)
        model_id = ""
        model_reason = ""
    else:
        chosen_city, call, model_reason, model_id = chat
    best = max(options, key=lambda item: (item[1], -item[2], item[0]))
    areas: list[AreaOption] = []
    for bucket in rollups.values():
        project = bucket["best_project"]
        score = float(bucket["best_score"])
        usd = _decimal(str(bucket["usd"]))
        city = str(bucket["city"])
        recommended = city == chosen_city
        band = [item for item in options if item[1] >= best[1] - _CLOSE_BAND]
        richest = max(band, key=lambda item: item[2]) if band else best
        if recommended and model_id:
            reason = (
                f"{model_id} chose {city}. Similarity {score:.0%}. "
                f"World Bank on record here is {_compact_money(usd)}."
            )
        elif recommended and call == "thinner_coverage":
            reason = (
                f"Close to this proposal, and less World Bank money is already on record here "
                f"({_compact_money(usd)}) than in {richest[0]} ({_compact_money(richest[2])})."
            )
        elif recommended and call == "closest_work":
            reason = (
                f"Nearest existing work"
                f"{f' ({project.name})' if isinstance(project, CatalogProject) else ''}. "
                "Other named cities are not close enough to send this budget toward thinner coverage."
            )
        elif recommended:
            reason = "Nearest text in this country, but the match is weak. Confirm the city before directing money."
        elif isinstance(project, CatalogProject) and score > 0:
            reason = (
                f"Similarity {score:.0%} on {project.name}. "
                f"World Bank on record here is {_compact_money(usd)}."
            )
        else:
            reason = f"No close project text in this city. World Bank on record here is {_compact_money(usd)}."
        areas.append(
            AreaOption(
                country=str(bucket["country"]),
                city=city,
                project_count=int(bucket["count"]),
                worldbank_usd=_money(usd),
                relevance=round(score, 2),
                nearest_project_id=project.project_id if isinstance(project, CatalogProject) else None,
                nearest_project_name=project.name if isinstance(project, CatalogProject) else None,
                nearest_source_url=project.source_url if isinstance(project, CatalogProject) else None,
                recommended=recommended,
                reason=reason,
            )
        )
    areas.sort(key=lambda item: (item.recommended, item.relevance, item.city), reverse=True)
    if model_id:
        summary = f"{model_id} recommends {chosen_city}."
    elif call == "thinner_coverage":
        summary = (
            f"Recommend {chosen_city}. The proposal is close to work already there, "
            "and that city has less World Bank funding on record."
        )
    elif call == "closest_work":
        summary = f"Recommend {chosen_city}. That is where this proposal sits closest to existing projects."
    else:
        summary = (
            f"No city is a close match. The nearest text is in {chosen_city}. "
            "Confirm the city yourself before directing money."
        )
    method = (
        "Nearest projects come from the local Chroma index."
        if used_chroma
        else "The project index was unavailable, so this rank uses shared words in the World Bank text."
    )
    if model_id:
        decider = f"The city was chosen by the local chat model {model_id} through Ollama. That run has no API charge."
    else:
        decider = "The local chat model was unavailable, so the coverage rule chose the city."
    return CatalogRecommendation(
        country=_clean(query.country),
        recommended_city=chosen_city,
        call=call,
        summary=summary,
        note=(
            f"{decider} {method} City totals are the sum of amount_usd on World Bank records that name the city. "
            "This is coverage in that snapshot, not a poverty index. Nothing is directed until you choose."
        ),
        areas=areas,
        model_id=model_id,
    )


def _decimal(value: str) -> Decimal:
    try:
        return Decimal(value or "0")
    except InvalidOperation:
        return Decimal(0)


def _money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def _split(amount: Decimal, weights: list[Decimal]) -> list[Decimal]:
    if not weights:
        return []
    usable = weights if sum(weights) > 0 else [Decimal(1)] * len(weights)
    total = sum(usable)
    cents = int((amount * 100).to_integral_value(rounding=ROUND_DOWN))
    shares = [int((Decimal(cents) * weight / total).to_integral_value(rounding=ROUND_DOWN)) for weight in usable]
    leftover = cents - sum(shares)
    order = sorted(range(len(usable)), key=lambda index: usable[index], reverse=True)
    for step in range(leftover):
        shares[order[step % len(order)]] += 1
    return [Decimal(share) / Decimal(100) for share in shares]


def funding_impact(
    title: str,
    country: str,
    city: str,
    amount_usd: Decimal | str,
    project_ids: list[str] | None = None,
) -> FundingImpact:
    """Show how a directed budget changes visible funding for matched World Bank projects."""
    amount = _decimal(str(amount_usd))
    compared = compare_catalog(
        CatalogCompareRequest(title=title, description=title, country=country, city=city, sector=title),
        limit=None,
    )
    wanted = set(project_ids or [])
    matches = [item for item in compared.matches if item.project.project_id in wanted] if wanted else compared.matches[:5]
    if not matches:
        matches = compared.matches[:5]
    overlapping = [item for item in matches if item.same_city and item.label == "OVERLAPPING"]
    shares = _split(amount, [_decimal(item.project.amount_usd) for item in overlapping])
    share_by_id = {item.project.project_id: share for item, share in zip(overlapping, shares, strict=True)}
    lines: list[ProjectImpact] = []
    for item in matches:
        worldbank = _decimal(item.project.amount_usd)
        added = share_by_id.get(item.project.project_id, Decimal(0))
        co_finance = item.project.project_id in share_by_id
        lines.append(
            ProjectImpact(
                project_id=item.project.project_id,
                name=item.project.name,
                source_url=item.project.source_url,
                label=item.label,
                worldbank_amount_usd=_money(worldbank),
                added_usd=_money(added),
                combined_usd=_money(worldbank + added),
                connection=(
                    "Co-finance. This share is added to the same work in this city."
                    if co_finance
                    else "Complement. Related record. None of this budget is added to it."
                ),
            )
        )
    city_total = sum(_decimal(project.amount_usd) for project in list_projects(country, city, limit=40))
    return FundingImpact(
        worldbank_in_city_usd=_money(city_total),
        added_usd=_money(amount),
        after_usd=_money(city_total + amount),
        lines=lines,
    )
