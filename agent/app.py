"""FastAPI entrypoint for Atlas11's local service APIs."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from agent.gaps import (
    GapDataUnavailableError,
    GapRecordNotFoundError,
    get_gap_record,
    load_gap_records,
)
from agent.schemas import DistrictNeedRecord

app = FastAPI()


@app.get("/gaps", response_model=list[DistrictNeedRecord] | DistrictNeedRecord)
def get_gaps(
    district_id: str | None = None,
) -> list[DistrictNeedRecord] | DistrictNeedRecord:
    """Return validated district gap records, optionally for one canonical ID."""
    try:
        if district_id is None:
            return load_gap_records()
        return get_gap_record(district_id)
    except GapRecordNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except GapDataUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
