"""Build reproducible district need scores from local indicator and project inputs."""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
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


def _read_rows(path: Path) -> list[dict[str, str]]:
    """Read a UTF-8 CSV, retaining blank values for unavailable source facts."""
    with path.open(newline="", encoding="utf-8") as source_file:
        return list(csv.DictReader(source_file))


def _load_weights(path: Path, available_columns: set[str]) -> dict[str, float]:
    """Load validated non-negative indicator weights from the local JSON configuration."""
    with path.open(encoding="utf-8") as weights_file:
        raw_weights = json.load(weights_file)
    weights = {
        key: float(value)
        for key, value in raw_weights.items()
        if not key.startswith("_")
    }
    if not weights or set(weights) - available_columns:
        raise ValueError("Need-score weights must name available indicator columns")
    if any(not math.isfinite(weight) or weight < 0 for weight in weights.values()):
        raise ValueError("Need-score weights must be finite and non-negative")
    if not math.isclose(math.fsum(weights.values()), 1.0, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("Need-score weights must sum to 1")
    return dict(sorted(weights.items()))


def _float(row: dict[str, str], field_name: str) -> float:
    """Read a finite numeric source value without inventing a missing value."""
    value = row.get(field_name, "").strip()
    if not value:
        raise ValueError(
            f"Missing {field_name} for district_id={row.get('district_id', '')!r}"
        )
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"{field_name} must be finite")
    return parsed


def _bottom_quartile_threshold(values: list[float]) -> float:
    """Return the inclusive nearest-rank 25th-percentile threshold deterministically."""
    if not values:
        raise ValueError("Cannot calculate a funding quartile without districts")
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * 0.25) - 1)]


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
    district_ids = [row.get("district_id", "").strip() for row in indicators]
    if not all(district_ids) or len(set(district_ids)) != len(district_ids):
        raise ValueError(
            "District indicator data must have unique canonical district IDs"
        )

    weights = _load_weights(weights_path, set(indicators[0]))
    populations = {row["district_id"]: _float(row, "population") for row in indicators}
    if any(population <= 0 for population in populations.values()):
        raise ValueError("District populations must be positive")

    raw_values = {
        column: {row["district_id"]: _float(row, column) for row in indicators}
        for column in weights
    }
    normalized = {}
    for column, values in raw_values.items():
        lower, upper = min(values.values()), max(values.values())
        normalized[column] = {
            district_id: 0.0 if upper == lower else (value - lower) / (upper - lower)
            for district_id, value in values.items()
        }

    commitments: defaultdict[str, list[float]] = defaultdict(list)
    canonical_ids = set(district_ids)
    for project in _read_rows(projects_path):
        district_id = project.get("district", "")
        if district_id not in canonical_ids:
            continue
        amount = _float(project, "amount_usd")
        if amount < 0:
            raise ValueError("Project amounts must be non-negative")
        commitments[district_id].append(amount)

    funding_per_capita = {
        district_id: math.fsum(commitments[district_id]) / populations[district_id]
        for district_id in district_ids
    }
    quartile_threshold = _bottom_quartile_threshold(list(funding_per_capita.values()))
    output_rows: list[dict[str, str]] = []
    for indicator in sorted(indicators, key=lambda row: row["district_id"]):
        district_id = indicator["district_id"]
        need_score = math.fsum(
            weights[column] * normalized[column][district_id] for column in weights
        )
        amount = math.fsum(commitments[district_id])
        output_rows.append(
            {
                "district_id": district_id,
                "district_name": indicator.get("district_name", ""),
                "need_score": str(need_score),
                "funded_commitments_usd": str(amount),
                "commitments_per_capita": str(funding_per_capita[district_id]),
                "funding_gap": str(
                    need_score >= 0.6
                    and funding_per_capita[district_id] <= quartile_threshold
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
