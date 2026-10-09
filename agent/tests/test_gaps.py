"""Focused contract, loader, lookup, and tool tests for district gap records."""

import csv
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from hypothesis import given, strategies as st
from pydantic import ValidationError

import agent.app as app_module
from agent.gaps import (
    GAP_RECORD_FIELDS,
    GapDataUnavailableError,
    GapRecordNotFoundError,
    get_gap_record,
    load_gap_records,
)
from agent.schemas import DistrictNeedRecord, IndicatorQuality
from agent.tools import district_need as district_need_tool
from agent.tools.district_need import DistrictNeedNotFoundError


def _record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "district_id": "district-a",
        "district_name": "District A",
        "need_score": 0.7,
        "funded_commitments_usd": 1250.0,
        "commitments_per_capita": 12.5,
        "funding_gap": True,
        "indicator_quality": "measured",
        "snapshot_date": "2025-01-15",
        "source": "seeded",
        "source_url": "local://gap-records",
    }
    record.update(overrides)
    return record


def _write_records(
    path: Path,
    rows: list[dict[str, object]],
    headers: tuple[str, ...] = GAP_RECORD_FIELDS,
) -> None:
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def test_load_gap_records_validates_rows_and_sorts_ids(tmp_path: Path) -> None:
    source_path = tmp_path / "need_scores.csv"
    _write_records(
        source_path,
        [
            _record(district_id="district-z", funding_gap=False),
            _record(district_id="district-a"),
        ],
    )

    records = load_gap_records(source_path)

    assert [record.district_id for record in records] == ["district-a", "district-z"]
    assert records[0].need_score == 0.7
    assert records[0].indicator_quality is IndicatorQuality.MEASURED
    assert records[0].funding_gap is True


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("district_id", "district id"),
        ("district_name", "   "),
        ("need_score", -0.01),
        ("need_score", 1.01),
        ("need_score", float("nan")),
        ("funded_commitments_usd", -1.0),
        ("commitments_per_capita", float("inf")),
        ("indicator_quality", "unknown"),
        ("snapshot_date", "15-01-2025"),
        ("source", "   "),
        ("source_url", "   "),
    ],
)
def test_district_need_record_rejects_each_invalid_contract_dimension(
    field: str, invalid_value: object
) -> None:
    with pytest.raises(ValidationError):
        DistrictNeedRecord.model_validate(_record(**{field: invalid_value}))


@given(
    district_id=st.from_regex(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,8}", fullmatch=True),
    need_score=st.floats(
        min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
    ),
    commitments=st.floats(
        min_value=0.0, max_value=1_000_000, allow_nan=False, allow_infinity=False
    ),
    funding_gap=st.booleans(),
    quality=st.sampled_from(list(IndicatorQuality)),
    snapshot_date=st.sampled_from(["2025-01-15", "TBD: needs source"]),
)
def test_district_need_record_contract_preserves_valid_generated_values(
    district_id: str,
    need_score: float,
    commitments: float,
    funding_gap: bool,
    quality: IndicatorQuality,
    snapshot_date: str,
) -> None:
    """Feature: gap-finder, Property 8: District Need Record contract validation."""
    record = DistrictNeedRecord.model_validate(
        _record(
            district_id=district_id,
            need_score=need_score,
            funded_commitments_usd=commitments,
            commitments_per_capita=commitments / 10,
            funding_gap=funding_gap,
            indicator_quality=quality,
            snapshot_date=snapshot_date,
        )
    )

    assert record.district_id == district_id
    assert record.need_score == need_score
    assert record.funded_commitments_usd == commitments
    assert record.funding_gap is funding_gap
    assert record.indicator_quality is quality
    assert record.snapshot_date == snapshot_date


@pytest.mark.parametrize(
    "headers",
    [
        GAP_RECORD_FIELDS[:-1],
        (GAP_RECORD_FIELDS[-1],) + GAP_RECORD_FIELDS[:-1],
        GAP_RECORD_FIELDS + ("unexpected",),
    ],
)
def test_load_gap_records_rejects_missing_reordered_or_extra_headers(
    tmp_path: Path, headers: tuple[str, ...]
) -> None:
    source_path = tmp_path / "need_scores.csv"
    row = _record()
    _write_records(
        source_path, [{name: row.get(name, "value") for name in headers}], headers
    )

    with pytest.raises(GapDataUnavailableError, match="CSV headers"):
        load_gap_records(source_path)


def test_load_gap_records_rejects_duplicate_ids_and_never_returns_partial_data(
    tmp_path: Path,
) -> None:
    duplicate_path = tmp_path / "duplicate.csv"
    _write_records(duplicate_path, [_record(), _record(district_name="Repeated")])
    with pytest.raises(GapDataUnavailableError, match="duplicate district_id"):
        load_gap_records(duplicate_path)

    invalid_path = tmp_path / "partially-invalid.csv"
    _write_records(
        invalid_path,
        [
            _record(district_id="district-a"),
            _record(district_id="district-b", need_score=2),
        ],
    )
    with pytest.raises(GapDataUnavailableError, match="CSV row 3 is invalid"):
        load_gap_records(invalid_path)


def test_load_gap_records_reports_an_unavailable_file(tmp_path: Path) -> None:
    with pytest.raises(GapDataUnavailableError, match="cannot be read"):
        load_gap_records(tmp_path / "missing.csv")


def test_get_gap_record_returns_known_records_and_rejects_unknown_ids(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "need_scores.csv"
    _write_records(source_path, [_record()])

    assert get_gap_record("district-a", source_path).district_name == "District A"
    with pytest.raises(GapRecordNotFoundError, match="district-missing"):
        get_gap_record("district-missing", source_path)
    with pytest.raises(GapRecordNotFoundError, match="not a canonical id"):
        get_gap_record("not a canonical id", source_path)


def test_district_need_delegates_and_converts_unknown_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = DistrictNeedRecord.model_validate(_record())
    calls: list[str] = []

    def get_known_record(district_id: str) -> DistrictNeedRecord:
        calls.append(district_id)
        return expected

    monkeypatch.setattr(district_need_tool, "get_gap_record", get_known_record)
    assert district_need_tool.district_need("district-a") is expected
    assert calls == ["district-a"]

    def raise_not_found(district_id: object) -> DistrictNeedRecord:
        raise GapRecordNotFoundError(district_id)

    monkeypatch.setattr(district_need_tool, "get_gap_record", raise_not_found)
    with pytest.raises(DistrictNeedNotFoundError, match="district-missing"):
        district_need_tool.district_need("district-missing")


def test_get_gaps_returns_validated_collection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = [
        DistrictNeedRecord.model_validate(_record(district_id="district-a")),
        DistrictNeedRecord.model_validate(_record(district_id="district-z")),
    ]
    monkeypatch.setattr(app_module, "load_gap_records", lambda: records)

    response = TestClient(app_module.app).get("/gaps")

    assert response.status_code == 200
    assert response.json() == [record.model_dump(mode="json") for record in records]


def test_get_gaps_returns_known_filtered_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = DistrictNeedRecord.model_validate(_record())
    requested_ids: list[str] = []

    def get_known_record(district_id: str) -> DistrictNeedRecord:
        requested_ids.append(district_id)
        return record

    monkeypatch.setattr(app_module, "get_gap_record", get_known_record)

    response = TestClient(app_module.app).get(
        "/gaps", params={"district_id": "district-a"}
    )

    assert response.status_code == 200
    assert response.json() == record.model_dump(mode="json")
    assert requested_ids == ["district-a"]


def test_get_gaps_maps_unknown_filtered_record_to_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_not_found(district_id: str) -> DistrictNeedRecord:
        raise GapRecordNotFoundError(district_id)

    monkeypatch.setattr(app_module, "get_gap_record", raise_not_found)

    response = TestClient(app_module.app).get(
        "/gaps", params={"district_id": "district-missing"}
    )

    assert response.status_code == 404
    assert "district-missing" in response.json()["detail"]


def test_get_gaps_maps_missing_source_to_service_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_missing_source() -> list[DistrictNeedRecord]:
        raise GapDataUnavailableError("Gap data unavailable: source file is missing")

    monkeypatch.setattr(app_module, "load_gap_records", raise_missing_source)

    response = TestClient(app_module.app).get("/gaps")

    assert response.status_code == 503
    assert "source file is missing" in response.json()["detail"]


def test_get_gaps_maps_malformed_source_to_service_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_malformed_source(district_id: str) -> DistrictNeedRecord:
        raise GapDataUnavailableError("Gap data unavailable: malformed CSV")

    monkeypatch.setattr(app_module, "get_gap_record", raise_malformed_source)

    response = TestClient(app_module.app).get(
        "/gaps", params={"district_id": "district-a"}
    )

    assert response.status_code == 503
    assert "malformed CSV" in response.json()["detail"]
