"""Focused coverage for reproducible local district need-score generation."""

import csv
import importlib.util
import math
from pathlib import Path

import pytest
from hypothesis import given, strategies as st


_builder_path = Path(__file__).resolve().parents[2] / "scripts" / "build_need_scores.py"
_builder_spec = importlib.util.spec_from_file_location(
    "build_need_scores", _builder_path
)
assert _builder_spec and _builder_spec.loader
_builder = importlib.util.module_from_spec(_builder_spec)
_builder_spec.loader.exec_module(_builder)
aggregate_commitments = _builder.aggregate_commitments
build_need_scores = _builder.build_need_scores
calculate_need_scores = _builder.calculate_need_scores
classify_funding_gap = _builder.classify_funding_gap
min_max_normalize = _builder.min_max_normalize
nearest_rank_bottom_quartile = _builder.nearest_rank_bottom_quartile
validate_canonical_district_ids = _builder.validate_canonical_district_ids
validate_indicator_rows = _builder.validate_indicator_rows
validate_weights = _builder.validate_weights


def _indicator_row(**overrides: str) -> dict[str, str]:
    row = {
        "district_id": "district-a",
        "district_name": "District A",
        "population": "100",
        "indicator_quality": "illustrative",
        "source": "seeded",
        "source_url": "local://indicators",
        "indicator": "0.5",
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize(
    "district_id", ["", " district-a", ".district-a", "district a"]
)
def test_validate_canonical_district_ids_rejects_invalid_ids(district_id: str) -> None:
    with pytest.raises(ValueError, match="canonical district_id"):
        validate_canonical_district_ids([{"district_id": district_id}])


def test_validate_canonical_district_ids_accepts_unique_opaque_ids_and_rejects_duplicates() -> (
    None
):
    rows = [{"district_id": "d-1"}, {"district_id": "region:two.3"}]

    assert validate_canonical_district_ids(rows) == ["d-1", "region:two.3"]
    with pytest.raises(ValueError, match="unique canonical"):
        validate_canonical_district_ids(rows + [{"district_id": "d-1"}])


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"district_name": ""}, "district_name"),
        ({"population": "0"}, "population must be positive"),
        ({"population": "NaN"}, "population must be finite"),
        ({"indicator_quality": "unknown"}, "indicator_quality"),
        ({"source": ""}, "source and source_url"),
        ({"indicator": ""}, "Missing indicator"),
        ({"indicator": "inf"}, "indicator must be finite"),
    ],
)
def test_validate_indicator_rows_rejects_invalid_required_values(
    overrides: dict[str, str], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_indicator_rows([_indicator_row(**overrides)], {"indicator": 1.0})


@pytest.mark.parametrize(
    "raw_weights",
    [
        {"missing": 1.0},
        {"indicator": "NaN"},
        {"indicator": float("inf")},
        {"indicator": -0.1},
        {"indicator": 0.9},
        {"_note": "metadata"},
    ],
)
def test_validate_weights_rejects_invalid_or_incomplete_configuration(
    raw_weights: object,
) -> None:
    with pytest.raises(ValueError):
        validate_weights(raw_weights, {"indicator"})


def test_validate_weights_ignores_metadata_and_returns_sorted_columns() -> None:
    weights = validate_weights(
        {"z_indicator": 0.4, "_note": "local configuration", "a_indicator": 0.6},
        {"a_indicator", "z_indicator"},
    )

    assert weights == {"a_indicator": 0.6, "z_indicator": 0.4}


@given(
    first=st.lists(
        st.floats(
            min_value=-1_000_000,
            max_value=1_000_000,
            allow_nan=False,
            allow_infinity=False,
        ),
        min_size=2,
        max_size=8,
    ),
    second=st.lists(
        st.floats(
            min_value=-1_000_000,
            max_value=1_000_000,
            allow_nan=False,
            allow_infinity=False,
        ),
        min_size=2,
        max_size=8,
    ),
)
def test_normalized_values_and_weighted_scores_are_finite_and_bounded(
    first: list[float], second: list[float]
) -> None:
    size = min(len(first), len(second))
    district_ids = [f"district-{index}" for index in range(size)]
    normalized = {
        "first": min_max_normalize(dict(zip(district_ids, first[:size]))),
        "second": min_max_normalize(dict(zip(district_ids, second[:size]))),
    }

    scores = calculate_need_scores(
        normalized, {"first": 0.4, "second": 0.6}, district_ids
    )

    assert all(
        math.isfinite(value) and 0.0 <= value <= 1.0
        for values in normalized.values()
        for value in values.values()
    )
    assert all(
        math.isfinite(score) and 0.0 <= score <= 1.0 for score in scores.values()
    )


@given(
    value=st.floats(
        min_value=-1_000_000, max_value=1_000_000, allow_nan=False, allow_infinity=False
    ),
    size=st.integers(min_value=1, max_value=8),
)
def test_constant_indicators_normalize_to_zero(value: float, size: int) -> None:
    values = {f"district-{index}": value for index in range(size)}

    assert min_max_normalize(values) == {district_id: 0.0 for district_id in values}


@given(
    baseline=st.floats(
        min_value=-1_000_000, max_value=1_000_000, allow_nan=False, allow_infinity=False
    ),
    other=st.floats(
        min_value=-1_000_000, max_value=1_000_000, allow_nan=False, allow_infinity=False
    ),
    increase=st.floats(
        min_value=0, max_value=1_000_000, allow_nan=False, allow_infinity=False
    ),
)
def test_increasing_a_positive_weight_indicator_cannot_lower_its_score(
    baseline: float, other: float, increase: float
) -> None:
    before = {"district-a": baseline, "district-b": other}
    after = {"district-a": baseline + increase, "district-b": other}
    weights = {"indicator": 1.0}

    before_score = calculate_need_scores(
        {"indicator": min_max_normalize(before)}, weights, before
    )["district-a"]
    after_score = calculate_need_scores(
        {"indicator": min_max_normalize(after)}, weights, after
    )["district-a"]

    assert after_score >= before_score


def test_aggregate_commitments_uses_only_exact_canonical_assignments() -> None:
    commitments = aggregate_commitments(
        [
            {"project_id": "first", "district": "district-a", "amount_usd": "125"},
            {"project_id": "second", "district": "district-a", "amount_usd": "75"},
            {
                "project_id": "display-name",
                "district": "District A",
                "amount_usd": "900",
            },
            {
                "project_id": "unmatched-invalid",
                "district": "district-z",
                "amount_usd": "NaN",
            },
            {"project_id": "missing", "amount_usd": "500"},
        ],
        ["district-a", "district-b"],
    )

    assert commitments == {"district-a": 200.0, "district-b": 0.0}
    with pytest.raises(ValueError, match="project row 2"):
        aggregate_commitments(
            [{"project_id": "invalid", "district": "district-a", "amount_usd": "-1"}],
            ["district-a"],
        )


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([7.0], 7.0),
        ([4.0, 1.0], 1.0),
        ([4.0, 3.0, 2.0, 1.0], 1.0),
        ([3.0, 1.0, 1.0, 2.0], 1.0),
    ],
)
def test_per_capita_quartile_and_gap_classification(
    values: list[float], expected: float
) -> None:
    commitments = aggregate_commitments(
        [
            {"project_id": "a", "district": "district-a", "amount_usd": "100"},
            {"project_id": "b", "district": "district-b", "amount_usd": "50"},
        ],
        ["district-a", "district-b"],
    )
    per_capita = {
        "district-a": commitments["district-a"] / 100,
        "district-b": commitments["district-b"] / 100,
    }

    assert per_capita == {"district-a": 1.0, "district-b": 0.5}
    assert nearest_rank_bottom_quartile(values) == expected
    assert classify_funding_gap(0.6, expected, expected)
    assert classify_funding_gap(0.7, expected - 0.001, expected)
    assert not classify_funding_gap(0.599, expected, expected)
    assert not classify_funding_gap(0.6, expected + 0.001, expected)


@given(
    need_score=st.floats(
        min_value=0, max_value=1, allow_nan=False, allow_infinity=False
    ),
    per_capita=st.floats(
        min_value=0, max_value=1_000_000, allow_nan=False, allow_infinity=False
    ),
    threshold=st.floats(
        min_value=0, max_value=1_000_000, allow_nan=False, allow_infinity=False
    ),
)
def test_gap_classification_matches_its_inclusive_definition(
    need_score: float, per_capita: float, threshold: float
) -> None:
    assert classify_funding_gap(need_score, per_capita, threshold) == (
        need_score >= 0.6 and per_capita <= threshold
    )


def test_build_need_scores_uses_exact_canonical_district_ids_and_preserves_provenance(
    tmp_path: Path,
) -> None:
    indicators_path = tmp_path / "district_indicators.csv"
    indicators_path.write_text(
        "district_id,district_name,population,population_density,informal_settlement_share,flood_exposure,transport_access_gap,indicator_quality,snapshot_date,source,source_url\n"
        "district-a,District A,100,0,0,0,0,illustrative,2025-01-01,seeded,local://indicators\n"
        "district-b,District B,100,1,1,1,1,estimated,TBD: needs source,seeded,local://indicators\n"
        "district-c,District C,100,0.8,0.8,0.8,0.8,illustrative,2025-01-01,seeded,local://indicators\n",
        encoding="utf-8",
    )
    projects_path = tmp_path / "projects.csv"
    projects_path.write_text(
        "project_id,district,amount_usd\n"
        "exact,district-a,100\n"
        "not-canonical,District A,900\n"
        "unmatched,district-z,500\n",
        encoding="utf-8",
    )
    weights_path = tmp_path / "need_weights.json"
    weights_path.write_text(
        '{"population_density": 0.25, "informal_settlement_share": 0.35, '
        '"flood_exposure": 0.25, "transport_access_gap": 0.15}',
        encoding="utf-8",
    )
    districts_geojson_path = tmp_path / "districts.geojson"
    districts_geojson_path.write_text(
        '{"type":"FeatureCollection","features":['
        '{"type":"Feature","properties":{"district_id":"district-a"}},'
        '{"type":"Feature","properties":{"district_id":"district-b"}},'
        '{"type":"Feature","properties":{"district_id":"district-c"}}]}',
        encoding="utf-8",
    )
    output_path = tmp_path / "need_scores.csv"

    build_need_scores(
        districts_geojson_path,
        indicators_path,
        projects_path,
        weights_path,
        output_path,
    )

    with output_path.open(newline="", encoding="utf-8") as output_file:
        rows = {row["district_id"]: row for row in csv.DictReader(output_file)}
    assert list(rows) == ["district-a", "district-b", "district-c"]
    assert rows["district-a"]["funded_commitments_usd"] == "100.0"
    assert rows["district-a"]["commitments_per_capita"] == "1.0"
    assert rows["district-c"]["funded_commitments_usd"] == "0.0"
    assert rows["district-c"]["need_score"] == "0.8"
    assert rows["district-c"]["funding_gap"] == "true"
    assert rows["district-a"]["funding_gap"] == "false"
    assert rows["district-c"]["indicator_quality"] == "illustrative"
    assert rows["district-c"]["snapshot_date"] == "2025-01-01"
    assert rows["district-c"]["source"] == "seeded"
    assert rows["district-c"]["source_url"] == "local://indicators"
