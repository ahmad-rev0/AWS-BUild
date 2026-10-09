"""Return recorded local need and funding facts for one canonical district; never infer missing data."""

from __future__ import annotations

from agent.gaps import GapRecordNotFoundError, get_gap_record
from agent.schemas import DistrictNeedRecord


class DistrictNeedNotFoundError(GapRecordNotFoundError):
    """Raised when local need-score data has no record for a canonical district ID."""


def district_need(district_id: str) -> DistrictNeedRecord:
    """Look up locally recorded need and current funding facts for a canonical district ID.

    Use this only to inspect existing local data. A result reports current recorded
    commitments and any gap flag; it never predicts, allocates, transfers, or claims
    funding for a district. Unknown IDs raise a typed not-found error.
    """
    try:
        return get_gap_record(district_id)
    except GapRecordNotFoundError as error:
        raise DistrictNeedNotFoundError(district_id) from error
