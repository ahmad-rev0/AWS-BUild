"""Validated, deterministic retrieval over the local persistent Chroma project index."""

from __future__ import annotations

import math
from datetime import date
from pathlib import Path
from typing import TypedDict, cast

from agent.config import PipelineConfig
from agent.embeddings import create_embedding_provider
from agent.errors import EmbeddingProviderError, SearchInputError
from agent.schemas import Candidate

ROOT = Path(__file__).resolve().parents[1]


class SearchFilters(TypedDict, total=False):
    """Optional exact geography and inclusive implementation-date constraints."""

    city: str
    district: str
    approval_date_from: date
    approval_date_to: date
    closing_date_from: date
    closing_date_to: date


_ALLOWED_FILTERS = frozenset(SearchFilters.__annotations__)
_DATE_FILTERS = frozenset(_ALLOWED_FILTERS - {"city", "district"})


def normalize_distance(distance: float) -> float:
    """Convert a Chroma distance to a finite normalized similarity score."""
    if not math.isfinite(distance):
        return 0.0
    return max(0.0, min(1.0, 1.0 - distance))


def _parse_date(value: object, key: str) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as error:
            raise SearchInputError(f"{key} must be an ISO date.") from error
    raise SearchInputError(f"{key} must be an ISO date.")


def _validate(text: str, k: int, filters: SearchFilters | None) -> dict[str, object]:
    if not isinstance(text, str) or not text.strip() or len(text) > 10_000:
        raise SearchInputError(
            "Search text must contain 1 through 10,000 non-whitespace characters."
        )
    if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= 100:
        raise SearchInputError("k must be an integer from 1 through 100.")
    if filters is None:
        return {}
    if not isinstance(filters, dict):
        raise SearchInputError("filters must be a mapping of supported filter fields.")
    unsupported = set(filters) - _ALLOWED_FILTERS
    if unsupported:
        raise SearchInputError(
            f"Unsupported filter field(s): {', '.join(sorted(unsupported))}."
        )

    validated: dict[str, object] = {}
    for key, value in filters.items():
        if key in {"city", "district"}:
            if not isinstance(value, str):
                raise SearchInputError(f"{key} must be a string.")
            validated[key] = value
        elif key in _DATE_FILTERS:
            validated[key] = _parse_date(value, key)
    for prefix in ("approval_date", "closing_date"):
        start = cast(date | None, validated.get(f"{prefix}_from"))
        end = cast(date | None, validated.get(f"{prefix}_to"))
        if start is not None and end is not None and start > end:
            raise SearchInputError(f"{prefix}_from must not be after {prefix}_to.")
    return validated


def _collection(config: PipelineConfig) -> object:
    try:
        import chromadb

        return chromadb.PersistentClient(path=str(config.chroma_path)).get_collection(
            config.chroma_collection
        )
    except Exception as error:
        raise EmbeddingProviderError(
            "Persistent project index is unavailable."
        ) from error


def _metadata_date(metadata: dict[str, object], key: str) -> date | None:
    value = metadata.get(key)
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _matches(metadata: dict[str, object], filters: dict[str, object]) -> bool:
    for key in ("city", "district"):
        if key in filters and metadata.get(key) != filters[key]:
            return False
    if not any(key in filters for key in _DATE_FILTERS):
        return True
    approval = _metadata_date(metadata, "approval_date")
    closing = _metadata_date(metadata, "closing_date")
    if approval is None or closing is None or closing < approval:
        return False
    lower_bounds = [
        cast(date, filters[key])
        for key in ("approval_date_from", "closing_date_from")
        if key in filters
    ]
    upper_bounds = [
        cast(date, filters[key])
        for key in ("approval_date_to", "closing_date_to")
        if key in filters
    ]
    return (not lower_bounds or closing >= max(lower_bounds)) and (
        not upper_bounds or approval <= min(upper_bounds)
    )


def search(
    text: str, k: int = 8, filters: SearchFilters | None = None
) -> list[Candidate]:
    """Return unique, ordered candidates after exact and inclusive filter validation."""
    validated_filters = _validate(text, k, filters)
    config = PipelineConfig.from_environment(ROOT)
    provider = create_embedding_provider(config)
    collection = _collection(config)
    try:
        count = collection.count()
        if count == 0:
            return []
        result = collection.query(
            query_embeddings=[provider.embed_query(text)],
            n_results=count,
            include=["distances", "metadatas"],
        )
    except EmbeddingProviderError:
        raise
    except Exception as error:
        raise EmbeddingProviderError("Project retrieval query failed.") from error

    ids = result.get("ids", [[]])[0]
    distances = result.get("distances", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    best_scores: dict[str, float] = {}
    for project_id, distance, metadata in zip(ids, distances, metadatas, strict=False):
        if not isinstance(project_id, str) or not isinstance(metadata, dict):
            continue
        if not _matches(metadata, validated_filters):
            continue
        try:
            score = normalize_distance(float(distance))
        except (TypeError, ValueError):
            score = 0.0
        best_scores[project_id] = max(score, best_scores.get(project_id, 0.0))
    return [
        Candidate(project_id=project_id, score=score)
        for project_id, score in sorted(
            best_scores.items(), key=lambda item: (-item[1], item[0])
        )[:k]
    ]
