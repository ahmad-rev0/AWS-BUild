"""FastAPI entrypoint for Atlas11's local coordination-demo API."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from agent.gaps import (
    GapDataUnavailableError,
    GapRecordNotFoundError,
    get_gap_record,
    load_gap_records,
)
from agent.schemas import (
    Approval,
    ApprovalCreate,
    AuditEvent,
    ClashReport,
    DistrictNeedRecord,
    Proposal,
    ProposalCreate,
    ProposalStatus,
    ReviewCreated,
    ReviewReportResponse,
    Role,
    SseEvent,
)
from agent.store import SQLiteStore, StoreConflictError, StoreNotFoundError

ROOT = Path(__file__).resolve().parents[1]
CACHE_PATH = ROOT / "data" / "demo_cache" / "demo-city-transit-01.json"
DATABASE_PATH = Path(os.getenv("ATLAS11_DB_PATH", str(ROOT / "data" / "atlas11.db")))
app = FastAPI(title="Atlas11 API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
store = SQLiteStore(DATABASE_PATH)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _audit(
    event_type: str,
    proposal_id: str | None = None,
    review_id: str | None = None,
    actor: str | None = None,
    role: Role | None = None,
    approval_id: str | None = None,
    project_id: str | None = None,
) -> AuditEvent:
    return AuditEvent(
        event_id=f"audit-{uuid4().hex}",
        event_type=event_type,
        timestamp=_now(),
        proposal_id=proposal_id,
        review_id=review_id,
        approval_id=approval_id,
        project_id=project_id,
        actor=actor,
        role=role,
        payload_summary=f"{event_type.replace('_', ' ')} recorded for coordination workflow.",
    )


def _cache() -> tuple[ProposalCreate, ClashReport]:
    try:
        payload = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        proposal = ProposalCreate.model_validate(payload["proposal"])
        report = ClashReport.model_validate(payload["report"])
    except (OSError, KeyError, json.JSONDecodeError, ValidationError) as error:
        raise HTTPException(
            status_code=503, detail="Cached demo data is unavailable or invalid."
        ) from error
    labels = [item.label.value for item in report.candidates]
    if (
        labels.count("OVERLAPPING") != 1
        or labels.count("COMPLEMENTARY") != 1
        or len(labels) != 2
        or report.memo.recommendation.value != "CO_FINANCE"
    ):
        raise HTTPException(
            status_code=503,
            detail="Cached demo report does not match the required scenario.",
        )
    return proposal, report


def _same_demo_submission(item: ProposalCreate, expected: ProposalCreate) -> bool:
    return item.model_dump(mode="json", exclude_none=False) == expected.model_dump(
        mode="json", exclude_none=False
    )


@app.post("/proposals", response_model=Proposal, status_code=status.HTTP_201_CREATED)
def create_proposal(item: ProposalCreate) -> Proposal:
    """Persist a proposal; cached mode accepts only the canonical seeded scenario."""
    proposal_id = f"proposal-{uuid4().hex[:12]}"
    if item.source == "seeded" or item.scenario_key == "demo-city-transit-01":
        expected, _ = _cache()
        if not _same_demo_submission(item, expected):
            raise HTTPException(
                status_code=422,
                detail="Seeded demo submission must match the canonical scenario.",
            )
        proposal_id = "demo-proposal-01"
    proposal = Proposal(
        **item.model_dump(),
        proposal_id=proposal_id,
        status=ProposalStatus.SUBMITTED,
        submitted_at=_now(),
    )
    try:
        return store.create_proposal(
            proposal,
            _audit(
                "proposal_submitted", proposal_id, actor="planner", role=Role.PLANNER
            ),
        )
    except StoreConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post(
    "/proposals/{proposal_id}/review",
    response_model=ReviewCreated,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_review(proposal_id: str) -> ReviewCreated:
    """Create a pending review; cached reports are executed when their stream opens."""
    try:
        proposal = store.get_proposal(proposal_id)
        review_id = f"review-{uuid4().hex[:12]}"
        return store.create_review(
            review_id,
            proposal_id,
            proposal.source,
            _now().isoformat(),
            _audit("review_created", proposal_id, review_id),
        )
    except StoreNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except StoreConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


def _complete_cached_review(review_id: str) -> list[SseEvent]:
    proposal = store.get_proposal_for_review(review_id)
    if (
        proposal.proposal_id != "demo-proposal-01"
        or os.getenv("DEMO_MODE", "cached") != "cached"
    ):
        raise HTTPException(
            status_code=503,
            detail="Live review is unavailable; use DEMO_MODE=cached for the scripted demo.",
        )
    _, cached_report = _cache()
    events = [
        SseEvent(
            type="status",
            payload={"message": "Loading validated cached coordination review."},
        ),
        SseEvent(
            type="tool_call",
            name="cached_demo",
            ms=0,
            payload={
                "message": "Using local seeded scenario; no AWS or retrieval invoked."
            },
        ),
        *(
            SseEvent(type="verdict", payload=verdict.model_dump(mode="json"))
            for verdict in cached_report.candidates
        ),
        SseEvent(type="done", payload={"review_id": review_id}),
    ]
    try:
        store.complete_review(
            review_id,
            cached_report,
            _now().isoformat(),
            [
                _audit("review_completed", proposal.proposal_id, review_id),
                *[
                    _audit(
                        "verdict_recorded",
                        proposal.proposal_id,
                        review_id,
                        project_id=v.project_id,
                    )
                    for v in cached_report.candidates
                ],
            ],
        )
    except StoreConflictError:
        pass
    return events


@app.get("/reviews/{review_id}/events")
def review_events(review_id: str) -> StreamingResponse:
    """Stream the typed scripted review trace in required terminal-safe order."""
    try:
        try:
            report = store.get_completed_report(review_id)
            events = [
                SseEvent(
                    type="status", payload={"message": "Replaying completed review."}
                ),
                *(
                    SseEvent(type="verdict", payload=v.model_dump(mode="json"))
                    for v in report.candidates
                ),
                SseEvent(type="done", payload={"review_id": review_id}),
            ]
        except StoreConflictError:
            events = _complete_cached_review(review_id)
    except StoreNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    def stream() -> object:
        for event in events:
            yield f"event: review\ndata: {event.model_dump_json()}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/reviews/{review_id}", response_model=ReviewReportResponse)
def get_review(review_id: str) -> ReviewReportResponse:
    """Return only a validated completed report plus its persisted proposal."""
    try:
        report = store.get_completed_report(review_id)
        proposal = store.get_proposal_for_review(review_id)
        return ReviewReportResponse(
            review_id=review_id, proposal=proposal, report=report
        )
    except StoreNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except StoreConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/approvals", response_model=Approval, status_code=status.HTTP_201_CREATED)
def create_approval(item: ApprovalCreate) -> Approval:
    """Record an approver-only coordination sign-off; no funding behaviour exists."""
    if item.role is not Role.APPROVER:
        raise HTTPException(
            status_code=403,
            detail="Only an approver may record a coordination decision.",
        )
    try:
        proposal = store.get_proposal_for_review(item.review_id)
        approval = Approval(
            approval_id=f"approval-{uuid4().hex[:12]}",
            review_id=item.review_id,
            proposal_id=proposal.proposal_id,
            actor=item.actor,
            role=item.role,
            decision=item.decision,
            reason=item.reason,
            decided_at=_now(),
        )
        return store.record_approval(
            approval,
            item.role,
            _audit(
                "approval_recorded",
                proposal.proposal_id,
                item.review_id,
                item.actor,
                item.role,
                approval.approval_id,
            ),
        )
    except StoreNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except StoreConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/audit", response_model=list[AuditEvent])
def get_audit(
    proposal_id: str | None = None, review_id: str | None = None
) -> list[AuditEvent]:
    """Return append-only redacted coordination audit rows."""
    return store.list_audit(proposal_id, review_id)


@app.get("/gaps", response_model=list[DistrictNeedRecord] | DistrictNeedRecord)
def get_gaps(
    district_id: str | None = None,
) -> list[DistrictNeedRecord] | DistrictNeedRecord:
    """Return read-only district gap records without recalculation."""
    try:
        return (
            load_gap_records() if district_id is None else get_gap_record(district_id)
        )
    except GapRecordNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except GapDataUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
