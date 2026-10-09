"""Return recorded local need and funding facts for one canonical district; never infer missing data."""

from __future__ import annotations

import csv
from pathlib import Path

from pydantic import BaseModel, Field


NEED_SCORES_PATH = Path(__file__).resolve().parents[2] / "data" / "geo" / "need_scores.csv"


class DistrictNeedInput(BaseModel):
    """Input for looking up recorded need and funding context for one district."""

    district_id: str = Field(min_length=1)


class DistrictNeedOutput(BaseModel):
    """Recorded need score and existing funding context, not a funding outcome."""

    district_id: str = Field(min_length=1)
    need_score: float = Field(ge=0.0, le=1.0)
    funded_commitments_usd: float | None = Field(default=None, ge=0.0)
    commitments_per_capita: float | None = Field(default=None, ge=0.0)
    funding_gap: bool | None = None
    indicator_quality: str | None = None
    snapshot_date: str | None = None


class DistrictNeedNotFoundError(LookupError):
    """Raised when local need-score data has no record for a canonical district ID."""


def _optional_non_negative_float(row: dict[str, str], field_name: str) -> float | None:
    """Return a recorded non-negative numeric field or leave unavailable data unset."""
    value = row.get(field_name, "").strip()
    if not value:
        return None
    parsed = float(value)
    if parsed < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return parsed


def district_need(district_id: str) -> DistrictNeedOutput:
    """Look up locally recorded need and current funding facts for a canonical district ID.

    Use this only to inspect existing local data. A result reports current recorded
    commitments and any gap flag; it never predicts, allocates, transfers, or claims
    funding for a district. Unknown IDs raise a typed not-found error.
    """
    requested = DistrictNeedInput(district_id=district_id)

    if not NEED_SCORES_PATH.exists():
        raise DistrictNeedNotFoundError(
            f"No local need-score record is available for district_id={requested.district_id!r}"
        )

    with NEED_SCORES_PATH.open(newline="", encoding="utf-8") as need_scores_file:
        for row in csv.DictReader(need_scores_file):
            if row.get("district_id") != requested.district_id:
                continue
            return DistrictNeedOutput(
                district_id=requested.district_id,
                need_score=float(row["need_score"]),
                funded_commitments_usd=_optional_non_negative_float(row, "funded_commitments_usd"),
                commitments_per_capita=_optional_non_negative_float(row, "commitments_per_capita"),
                funding_gap=(row.get("funding_gap", "").strip().lower() == "true")
                if row.get("funding_gap", "").strip()
                else None,
                indicator_quality=row.get("indicator_quality") or None,
                snapshot_date=row.get("snapshot_date") or None,
            )

    raise DistrictNeedNotFoundError(
        f"No local need-score record is available for district_id={requested.district_id!r}"
    )
