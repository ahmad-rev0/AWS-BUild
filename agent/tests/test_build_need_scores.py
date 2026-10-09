"""Focused coverage for reproducible local district need-score generation."""

import csv
import importlib.util
from pathlib import Path


_builder_path = Path(__file__).resolve().parents[2] / "scripts" / "build_need_scores.py"
_builder_spec = importlib.util.spec_from_file_location(
    "build_need_scores", _builder_path
)
assert _builder_spec and _builder_spec.loader
_builder = importlib.util.module_from_spec(_builder_spec)
_builder_spec.loader.exec_module(_builder)
build_need_scores = _builder.build_need_scores


def test_build_need_scores_uses_exact_canonical_district_ids_and_preserves_provenance(
    tmp_path: Path,
) -> None:
    indicators_path = tmp_path / "district_indicators.csv"
    indicators_path.write_text(
        "district_id,district_name,population,population_density,informal_settlement_share,flood_exposure,transport_access_gap,indicator_quality,source,source_url\n"
        "district-a,District A,100,0,0,0,0,illustrative,seeded,local://indicators\n"
        "district-b,District B,100,1,1,1,1,estimated,seeded,local://indicators\n"
        "district-c,District C,100,0.8,0.8,0.8,0.8,illustrative,seeded,local://indicators\n",
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
    output_path = tmp_path / "need_scores.csv"

    build_need_scores(indicators_path, projects_path, weights_path, output_path)

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
    assert rows["district-c"]["snapshot_date"] == ""
    assert rows["district-c"]["source"] == "seeded"
    assert rows["district-c"]["source_url"] == "local://indicators"
