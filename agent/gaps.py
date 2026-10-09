"""Read-only, validated access to generated district funding-gap records."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from agent.errors import PipelineError
from agent.schemas import DistrictNeedRecord

ROOT: Final = Path(__file__).resolve().parents[1]
NEED_SCORES_PATH: Final = ROOT / "data" / "geo" / "need_scores.csv"
GAP_RECORD_FIELDS: Final = tuple(DistrictNeedRecord.model_fields)


class GapDataUnavailableError(PipelineError):
    """Raised when the complete generated gap dataset cannot be safely loaded."""


class GapRecordNotFoundError(PipelineError):
    """Raised when a district has no record in an otherwise valid gap dataset."""

    def __init__(self, district_id: object) -> None:
        super().__init__(f"Gap record not found: {district_id}")


def _unavailable(reason: str) -> GapDataUnavailableError:
    """Create a readable typed error without exposing parser implementation details."""
    return GapDataUnavailableError(f"Gap data unavailable: {reason}")


def load_gap_records(
    path: Path | str = NEED_SCORES_PATH,
) -> list[DistrictNeedRecord]:
    """Load every valid generated gap record in ascending canonical district-ID order."""
    source_path = Path(path)
    try:
        with source_path.open(newline="", encoding="utf-8") as source_file:
            reader = csv.DictReader(source_file)
            if tuple(reader.fieldnames or ()) != GAP_RECORD_FIELDS:
                raise _unavailable(
                    "CSV headers do not match the district gap record schema"
                )
            rows = list(reader)
    except GapDataUnavailableError:
        raise
    except (OSError, UnicodeError, csv.Error) as error:
        raise _unavailable("generated need-score CSV cannot be read") from error

    records: list[DistrictNeedRecord] = []
    district_ids: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        if set(row) != set(GAP_RECORD_FIELDS) or any(
            value is None for value in row.values()
        ):
            raise _unavailable(
                f"CSV row {row_number} does not match the district gap schema"
            )
        try:
            record = DistrictNeedRecord.model_validate(row)
        except ValidationError as error:
            raise _unavailable(f"CSV row {row_number} is invalid") from error
        if record.district_id in district_ids:
            raise _unavailable(
                f"CSV contains duplicate district_id: {record.district_id}"
            )
        district_ids.add(record.district_id)
        records.append(record)

    return sorted(records, key=lambda record: record.district_id)


def get_gap_record(
    district_id: object,
    path: Path | str = NEED_SCORES_PATH,
) -> DistrictNeedRecord:
    """Return one validated district gap record or raise a typed not-found error."""
    records = load_gap_records(path)
    try:
        DistrictNeedRecord.validate_canonical_values({"district_id": district_id})
    except ValueError as error:
        raise GapRecordNotFoundError(district_id) from error

    for record in records:
        if record.district_id == district_id:
            return record
    raise GapRecordNotFoundError(district_id)
