"""Build reproducible district need scores from local indicator and project inputs."""

from __future__ import annotations

import csv
import json
import math
import os
import sys
import tempfile
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.schemas import CANONICAL_ID_PATTERN, DistrictNeedRecord  # noqa: E402

DISTRICTS_GEOJSON_PATH: Final = ROOT / "data" / "geo" / "districts.geojson"
INDICATORS_PATH: Final = ROOT / "data" / "geo" / "district_indicators.csv"
PROJECTS_PATH: Final = ROOT / "data" / "processed" / "projects.csv"
WEIGHTS_PATH: Final = ROOT / "data" / "geo" / "need_weights.json"
OUTPUT_PATH: Final = ROOT / "data" / "geo" / "need_scores.csv"
DISTRICT_ID_PROPERTY: Final = "district_id"

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


def load_geojson_district_ids(path: Path) -> list[str]:
    """Load unique canonical district IDs from the configured local FeatureCollection."""
    try:
        with path.open(encoding="utf-8") as geojson_file:
            document = json.load(geojson_file)
    except OSError as error:
        raise ValueError(f"Unable to read district GeoJSON {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"District GeoJSON {path} is not valid JSON") from error

    if not isinstance(document, dict) or document.get("type") != "FeatureCollection":
        raise ValueError("District GeoJSON must be a FeatureCollection")
    features = document.get("features")
    if not isinstance(features, list):
        raise ValueError(
            "District GeoJSON FeatureCollection must contain a features array"
        )

    district_ids: list[str] = []
    for feature_number, feature in enumerate(features, start=1):
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise ValueError(f"District GeoJSON feature {feature_number} is invalid")
        properties = feature.get("properties")
        district_id = (
            properties.get(DISTRICT_ID_PROPERTY)
            if isinstance(properties, dict)
            else None
        )
        if (
            not isinstance(district_id, str)
            or not district_id
            or not CANONICAL_ID_PATTERN.fullmatch(district_id)
        ):
            raise ValueError(
                f"District GeoJSON feature {feature_number} has an invalid canonical "
                f"{DISTRICT_ID_PROPERTY}"
            )
        district_ids.append(district_id)

    if len(set(district_ids)) != len(district_ids):
        raise ValueError("District GeoJSON must have unique canonical district IDs")
    return district_ids


def validate_district_universe(
    geojson_ids: Iterable[str], indicator_ids: Iterable[str]
) -> None:
    """Require exact canonical district-ID agreement without inferred mappings."""
    geojson_set, indicator_set = set(geojson_ids), set(indicator_ids)
    missing_from_geojson = sorted(indicator_set - geojson_set)
    extra_in_geojson = sorted(geojson_set - indicator_set)
    if missing_from_geojson or extra_in_geojson:
        details: list[str] = []
        if missing_from_geojson:
            details.append(f"missing from GeoJSON: {missing_from_geojson}")
        if extra_in_geojson:
            details.append(f"extra in GeoJSON: {extra_in_geojson}")
        raise ValueError("District ID sets differ; " + "; ".join(details))


def validate_snapshot_dates(rows: Sequence[CsvRow]) -> dict[str, str]:
    """Preserve source dates or explicitly mark unavailable snapshot dates."""
    snapshot_dates: dict[str, str] = {}
    for row_number, row in enumerate(rows, start=2):
        district_id = row.get("district_id", "")
        value = row.get("snapshot_date", "")
        if not value or not value.strip():
            snapshot_dates[district_id] = "TBD: needs source"
            continue
        if value == "TBD: needs source":
            snapshot_dates[district_id] = value
            continue
        try:
            date.fromisoformat(value)
        except ValueError as error:
            raise ValueError(
                f"snapshot_date is invalid for district_id={district_id!r} "
                f"at indicator row {row_number}"
            ) from error
        snapshot_dates[district_id] = value
    return snapshot_dates


def _write_output_rows(output_path: Path, rows: Sequence[Mapping[str, str]]) -> None:
    """Publish complete CSV rows atomically without overwriting committed output early."""
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            newline="",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as output_file:
            temporary_path = Path(output_file.name)
            writer = csv.DictWriter(
                output_file, fieldnames=OUTPUT_FIELDS, lineterminator="\n"
            )
            writer.writeheader()
            writer.writerows(rows)
            output_file.flush()
            os.fsync(output_file.fileno())
        temporary_path.replace(output_path)
    except OSError as error:
        raise ValueError(f"Unable to publish need scores: {error}") from error
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def build_need_scores(
    districts_geojson_path: Path = DISTRICTS_GEOJSON_PATH,
    indicators_path: Path = INDICATORS_PATH,
    projects_path: Path = PROJECTS_PATH,
    weights_path: Path = WEIGHTS_PATH,
    output_path: Path = OUTPUT_PATH,
) -> list[dict[str, str]]:
    """Write deterministic local need scores without allocating unmatched project funding."""
    geojson_ids = load_geojson_district_ids(districts_geojson_path)
    indicators = _read_rows(indicators_path)
    if not indicators:
        raise ValueError("District indicator data must contain at least one district")
    district_ids = validate_canonical_district_ids(indicators)
    validate_district_universe(geojson_ids, district_ids)
    weights = _load_weights(weights_path, indicators[0])
    raw_values = validate_indicator_rows(indicators, weights)
    snapshot_dates = validate_snapshot_dates(indicators)
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

    records: list[DistrictNeedRecord] = []
    for indicator in sorted(indicators, key=lambda row: row["district_id"]):
        district_id = indicator["district_id"]
        need_score = need_scores[district_id]
        records.append(
            DistrictNeedRecord.model_validate(
                {
                    "district_id": district_id,
                    "district_name": indicator.get("district_name", ""),
                    "need_score": need_score,
                    "funded_commitments_usd": commitments[district_id],
                    "commitments_per_capita": funding_per_capita[district_id],
                    "funding_gap": classify_funding_gap(
                        need_score,
                        funding_per_capita[district_id],
                        quartile_threshold,
                    ),
                    "indicator_quality": indicator.get("indicator_quality", ""),
                    "snapshot_date": snapshot_dates[district_id],
                    "source": indicator.get("source", ""),
                    "source_url": indicator.get("source_url", ""),
                }
            )
        )

    output_rows = [
        {
            "district_id": record.district_id,
            "district_name": record.district_name,
            "need_score": str(record.need_score),
            "funded_commitments_usd": str(record.funded_commitments_usd),
            "commitments_per_capita": str(record.commitments_per_capita),
            "funding_gap": str(record.funding_gap).lower(),
            "indicator_quality": record.indicator_quality.value,
            "snapshot_date": record.snapshot_date,
            "source": record.source,
            "source_url": record.source_url,
        }
        for record in records
    ]

    _write_output_rows(output_path, output_rows)
    return output_rows


if __name__ == "__main__":
    build_need_scores()
