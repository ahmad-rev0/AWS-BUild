"""Build reproducible district need scores from local indicator and project inputs."""

from __future__ import annotations

import csv
import json
import math
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.schemas import CANONICAL_ID_PATTERN  # noqa: E402

INDICATORS_PATH: Final = ROOT / "data" / "geo" / "district_indicators.csv"
PROJECTS_PATH: Final = ROOT / "data" / "processed" / "projects.csv"
WEIGHTS_PATH: Final = ROOT / "data" / "geo" / "need_weights.json"
OUTPUT_PATH: Final = ROOT / "data" / "geo" / "need_scores.csv"

OUTPUT_FIELDS: Final = (
    "district_id",
    "district_name",
    "need_score",
    "funded_commitments_usd",
    "commitments_per_capita",
    "funding_gap",
    "indicator_quality",
    "snapshot_date",
    "source",
    "source_url",
)
INDICATOR_QUALITIES: Final = frozenset({"measured", "estimated", "illustrative"})


CsvRow = Mapping[str, str]


def _read_rows(path: Path) -> list[dict[str, str]]:
    """Read a UTF-8 CSV, retaining blank values for unavailable source facts."""
    with path.open(newline="", encoding="utf-8") as source_file:
        return list(csv.DictReader(source_file))


def validate_canonical_district_ids(rows: Sequence[CsvRow]) -> list[str]:
    """Return unique district IDs after enforcing the shared canonical-ID contract."""
    district_ids: list[str] = []
    for row_number, row in enumerate(rows, start=2):
        district_id = row.get("district_id", "")
        if not isinstance(district_id, str) or not CANONICAL_ID_PATTERN.fullmatch(
            district_id
        ):
            raise ValueError(
                f"District indicator row {row_number} has an invalid canonical district_id"
            )
        district_ids.append(district_id)

    if len(set(district_ids)) != len(district_ids):
        raise ValueError(
            "District indicator data must have unique canonical district IDs"
        )
    return district_ids


def _float(row: CsvRow, field_name: str, *, context: str) -> float:
    """Read a finite numeric source value without inventing a missing value."""
    value = row.get(field_name, "")
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing {field_name} for {context}")
    try:
        parsed = float(value)
    except ValueError as error:
        raise ValueError(f"{field_name} must be numeric for {context}") from error
    if not math.isfinite(parsed):
        raise ValueError(f"{field_name} must be finite for {context}")
    return parsed


def validate_indicator_rows(
    rows: Sequence[CsvRow], weights: Mapping[str, float]
) -> dict[str, dict[str, float]]:
    """Validate district metadata and configured finite indicator values by ID."""
    if not rows:
        raise ValueError("District indicator data must contain at least one district")

    district_ids = validate_canonical_district_ids(rows)
    values_by_indicator = {column: {} for column in weights}
    for row_number, (district_id, row) in enumerate(zip(district_ids, rows), start=2):
        context = f"district_id={district_id!r} at indicator row {row_number}"
        if not row.get("district_name", "").strip():
            raise ValueError(f"district_name must be non-empty for {context}")
        population = _float(row, "population", context=context)
        if population <= 0:
            raise ValueError(f"population must be positive for {context}")
        if row.get("indicator_quality", "").strip() not in INDICATOR_QUALITIES:
            raise ValueError(f"indicator_quality is invalid for {context}")
        if not row.get("source", "").strip() or not row.get("source_url", "").strip():
            raise ValueError(f"source and source_url must be retained for {context}")
        for column in weights:
            values_by_indicator[column][district_id] = _float(
                row, column, context=context
            )
    return values_by_indicator


def validate_weights(
    raw_weights: object, available_columns: Iterable[str]
) -> dict[str, float]:
    """Validate configured finite non-negative weights against available columns."""
    if not isinstance(raw_weights, dict):
        raise ValueError("Need-score weights must be a JSON object")
    available = set(available_columns)
    weights: dict[str, float] = {}
    for column, raw_weight in raw_weights.items():
        if not isinstance(column, str) or column.startswith("_"):
            continue
        if column not in available:
            raise ValueError(
                f"Need-score weight names unavailable indicator {column!r}"
            )
        try:
            weight = float(raw_weight)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"Need-score weight for {column!r} must be numeric"
            ) from error
        if not math.isfinite(weight) or weight < 0:
            raise ValueError(
                f"Need-score weight for {column!r} must be finite and non-negative"
            )
        weights[column] = weight

    if not weights:
        raise ValueError("Need-score weights must name available indicator columns")
    if not math.isclose(math.fsum(weights.values()), 1.0, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("Need-score weights must sum to 1 within 1e-12")
    return dict(sorted(weights.items()))


def _load_weights(path: Path, available_columns: Iterable[str]) -> dict[str, float]:
    """Load validated non-negative indicator weights from the local JSON configuration."""
    with path.open(encoding="utf-8") as weights_file:
        return validate_weights(json.load(weights_file), available_columns)


def min_max_normalize(values: Mapping[str, float]) -> dict[str, float]:
    """Normalize finite indicator values or return zeroes for a constant indicator."""
    if not values:
        raise ValueError("Cannot normalize an indicator without district values")
    if any(not math.isfinite(value) for value in values.values()):
        raise ValueError("Indicator values must be finite before normalization")
    lower, upper = min(values.values()), max(values.values())
    if upper == lower:
        return {district_id: 0.0 for district_id in values}
    return {
        district_id: (value - lower) / (upper - lower)
        for district_id, value in values.items()
    }


def calculate_need_scores(
    normalized_indicators: Mapping[str, Mapping[str, float]],
    weights: Mapping[str, float],
    district_ids: Iterable[str],
) -> dict[str, float]:
    """Calculate finite weighted need scores for the supplied canonical districts."""
    scores: dict[str, float] = {}
    for district_id in district_ids:
        score = math.fsum(
            weights[column] * normalized_indicators[column][district_id]
            for column in weights
        )
        if not math.isfinite(score) or not 0.0 <= score <= 1.0:
            raise ValueError(
                f"Need score must be finite and within [0, 1] for {district_id!r}"
            )
        scores[district_id] = score
    return scores


def aggregate_commitments(
    projects: Sequence[CsvRow], canonical_ids: Iterable[str]
) -> dict[str, float]:
    """Sum only non-negative commitments assigned to exact canonical district IDs."""
    districts = set(canonical_ids)
    commitments: defaultdict[str, list[float]] = defaultdict(list)
    for row_number, project in enumerate(projects, start=2):
        district_id = project.get("district", "")
        if district_id not in districts:
            continue
        project_id = project.get("project_id", "") or "unknown"
        context = f"project row {row_number} (project_id={project_id!r})"
        amount = _float(project, "amount_usd", context=context)
        if amount < 0:
            raise ValueError(f"amount_usd must be non-negative for {context}")
        commitments[district_id].append(amount)
    return {
        district_id: math.fsum(commitments[district_id]) for district_id in districts
    }


def nearest_rank_bottom_quartile(values: Sequence[float]) -> float:
    """Return the inclusive nearest-rank 25th-percentile threshold deterministically."""
    if not values:
        raise ValueError("Cannot calculate a funding quartile without districts")
    if any(not math.isfinite(value) for value in values):
        raise ValueError("Funding per-capita values must be finite")
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * 0.25) - 1)]


def classify_funding_gap(
    need_score: float, commitments_per_capita: float, quartile_threshold: float
) -> bool:
    """Classify a gap only from the specified score and inclusive quartile predicate."""
    return need_score >= 0.6 and commitments_per_capita <= quartile_threshold


def build_need_scores(
    indicators_path: Path = INDICATORS_PATH,
    projects_path: Path = PROJECTS_PATH,
    weights_path: Path = WEIGHTS_PATH,
    output_path: Path = OUTPUT_PATH,
) -> list[dict[str, str]]:
    """Write deterministic local need scores without allocating unmatched project funding."""
    indicators = _read_rows(indicators_path)
    if not indicators:
        raise ValueError("District indicator data must contain at least one district")
    weights = _load_weights(weights_path, indicators[0])
    raw_values = validate_indicator_rows(indicators, weights)
    district_ids = validate_canonical_district_ids(indicators)
    populations = {
        district_id: _float(
            row,
            "population",
            context=f"district_id={district_id!r} at indicator row {row_number}",
        )
        for row_number, (district_id, row) in enumerate(
            zip(district_ids, indicators), start=2
        )
    }
    normalized = {
        column: min_max_normalize(values) for column, values in raw_values.items()
    }
    need_scores = calculate_need_scores(normalized, weights, district_ids)
    commitments = aggregate_commitments(_read_rows(projects_path), district_ids)
    funding_per_capita = {
        district_id: commitments[district_id] / populations[district_id]
        for district_id in district_ids
    }
    quartile_threshold = nearest_rank_bottom_quartile(list(funding_per_capita.values()))

    output_rows: list[dict[str, str]] = []
    for indicator in sorted(indicators, key=lambda row: row["district_id"]):
        district_id = indicator["district_id"]
        need_score = need_scores[district_id]
        amount = commitments[district_id]
        output_rows.append(
            {
                "district_id": district_id,
                "district_name": indicator.get("district_name", ""),
                "need_score": str(need_score),
                "funded_commitments_usd": str(amount),
                "commitments_per_capita": str(funding_per_capita[district_id]),
                "funding_gap": str(
                    classify_funding_gap(
                        need_score, funding_per_capita[district_id], quartile_threshold
                    )
                ).lower(),
                "indicator_quality": indicator.get("indicator_quality", ""),
                "snapshot_date": "",
                "source": indicator.get("source", ""),
                "source_url": indicator.get("source_url", ""),
            }
        )

    with output_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(output_rows)
    return output_rows


if __name__ == "__main__":
    build_need_scores()
