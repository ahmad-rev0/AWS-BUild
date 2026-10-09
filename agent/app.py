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
from pydantic import BaseModel, ValidationError

from agent.catalog import (
    CatalogCommitRequest,
    CatalogCommitment,
    CatalogCompareRequest,
    CatalogCompareResponse,
    CatalogProject,
    CatalogSummary,
    CatalogUnavailableError,
    CatalogRecommendation,
    compare_catalog,
    list_projects,
    funding_impact,
    _place_key,
    named_city,
    projects_by_ids,
    recommend_catalog,
    summary as catalog_summary,
)
from agent.gaps import (
    GapDataUnavailableError,
    GapRecordNotFoundError,
    get_gap_record,
    load_gap_records,
)
from agent.schemas import (
    Approval,
    ApprovalCreate,
    Assignment,
    AssignmentCreate,
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
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
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


class ProposalWorkspace(BaseModel):
    """A proposal plus the latest review, report, decision, and district commitment."""

    proposal: Proposal
    review_id: str | None = None
    report: ClashReport | None = None
    approval: Approval | None = None
    assignment: Assignment | None = None


DEMO_PROPOSAL_ID = "demo-proposal-01"


@app.post("/demo/reset", status_code=status.HTTP_204_NO_CONTENT)
def reset_demo() -> None:
    """Clear only the scripted demo proposal so the walkthrough can be repeated."""
    store.reset_proposal(DEMO_PROPOSAL_ID)


@app.get("/proposals/{proposal_id}", response_model=ProposalWorkspace)
def get_proposal_workspace(proposal_id: str) -> ProposalWorkspace:
    """Reopen a stored proposal without creating a second cached submission."""
    try:
        proposal = store.get_proposal(proposal_id)
    except StoreNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    review_id = store.latest_review_id(proposal_id)
    report = None
    if review_id is not None:
        try:
            report = store.get_completed_report(review_id)
        except StoreConflictError:
            report = None
        except StoreNotFoundError:
            review_id = None
    return ProposalWorkspace(
        proposal=proposal,
        review_id=review_id,
        report=report,
        approval=store.latest_approval_for_proposal(proposal_id),
        assignment=store.latest_assignment_for_proposal(proposal_id),
    )


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


@app.post(
    "/proposals/{proposal_id}/assignment",
    response_model=Assignment,
    status_code=status.HTTP_201_CREATED,
)
def assign_proposal_budget(proposal_id: str, item: AssignmentCreate) -> Assignment:
    """Record this proposal's budget on the district the approver chooses."""
    if item.role is not Role.APPROVER:
        raise HTTPException(
            status_code=403,
            detail="Only an approver may commit a proposal budget to a district.",
        )
    try:
        get_gap_record(item.district_id)
        proposal = store.get_proposal(proposal_id)
    except GapRecordNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except StoreNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    assignment = Assignment(
        assignment_id=f"assignment-{uuid4().hex[:12]}",
        proposal_id=proposal.proposal_id,
        district_id=item.district_id,
        amount_usd=proposal.budget_usd,
        actor=item.actor,
        role=item.role,
        assigned_at=_now(),
    )
    audit = _audit(
        "budget_assigned",
        proposal.proposal_id,
        actor=item.actor,
        role=item.role,
    )
    audit.payload_summary = (
        f"Committed {proposal.budget_usd} from {proposal.proposal_id} to {item.district_id}."
    )
    try:
        return store.assign_budget(assignment, audit)
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


def _catalog_error(error: CatalogUnavailableError) -> HTTPException:
    return HTTPException(status_code=503, detail=str(error))


@app.get("/catalog", response_model=CatalogSummary)
def get_catalog() -> CatalogSummary:
    """Summarize the local World Bank Projects API snapshot by country and named city."""
    try:
        return catalog_summary()
    except CatalogUnavailableError as error:
        raise _catalog_error(error) from error


@app.get("/catalog/projects", response_model=list[CatalogProject])
def get_catalog_projects(
    country: str | None = None,
    city: str | None = None,
    unplaced: bool = False,
    limit: int = 12,
) -> list[CatalogProject]:
    """List World Bank project records. Rows without a city are included only when unplaced=true."""
    try:
        return list_projects(country, city, unplaced, max(1, min(limit, 40)))
    except CatalogUnavailableError as error:
        raise _catalog_error(error) from error


@app.post("/catalog/compare", response_model=CatalogCompareResponse)
def post_catalog_compare(payload: CatalogCompareRequest) -> CatalogCompareResponse:
    """Match proposal text to real World Bank records. This does not start the scripted review."""
    try:
        return compare_catalog(payload)
    except CatalogUnavailableError as error:
        raise _catalog_error(error) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except GapDataUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/catalog/recommend", response_model=CatalogRecommendation)
def post_catalog_recommend(payload: CatalogCompareRequest) -> CatalogRecommendation:
    """Rank named cities by proposal fit and existing World Bank coverage. Does not direct funds."""
    try:
        return recommend_catalog(payload)
    except CatalogUnavailableError as error:
        raise _catalog_error(error) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _human_decision(item: CatalogCommitRequest, city: str) -> tuple[str | None, str, str]:
    choice = item.human_choice.strip().lower() or "unreviewed"
    if choice not in {"accepted", "override", "unreviewed"}:
        raise HTTPException(status_code=422, detail="human_choice must be accepted, override, or unreviewed.")
    recommended = item.recommended_city.strip() if item.recommended_city else None
    note = " ".join(item.decision_note.split())
    if choice == "unreviewed":
        return None, "unreviewed", ""
    if not recommended:
        raise HTTPException(status_code=422, detail="A recommendation is required before accepting or overriding it.")
    same = _place_key(city) == _place_key(recommended)
    if choice == "accepted" and not same:
        raise HTTPException(status_code=422, detail="Accept applies only to the recommended city.")
    if choice == "override" and same:
        choice = "accepted"
    if choice == "override" and len(note) < 8:
        raise HTTPException(status_code=422, detail="Add a short reason for choosing a different city.")
    return recommended, choice, note if choice == "override" else ""


def _commitment_from_row(row: dict[str, object]) -> CatalogCommitment:
    project_ids = row["project_ids"]
    ids = project_ids if isinstance(project_ids, list) else []
    clean_ids = [str(item) for item in ids]
    title = str(row["title"])
    country = str(row["country"])
    city = str(row["city"])
    amount = str(row["amount_usd"])
    projects = projects_by_ids(clean_ids)
    return CatalogCommitment(
        commitment_id=str(row["commitment_id"]),
        country=country,
        city=city,
        title=title,
        amount_usd=amount,
        project_ids=clean_ids,
        created_at=str(row["created_at"]),
        projects=projects,
        impact=funding_impact(title, country, city, amount, clean_ids),
        recommended_city=str(row["recommended_city"]) if row.get("recommended_city") else None,
        human_choice=str(row.get("human_choice") or "unreviewed"),
        decision_note=str(row.get("decision_note") or ""),
    )


@app.post("/catalog/commit", response_model=CatalogCommitment, status_code=status.HTTP_201_CREATED)
def commit_catalog(item: CatalogCommitRequest) -> CatalogCommitment:
    """Direct a proposal budget to a city named in the World Bank snapshot."""
    try:
        city = named_city(item.country, item.city)
        projects = projects_by_ids(item.project_ids)
    except CatalogUnavailableError as error:
        raise _catalog_error(error) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    recommended, human_choice, decision_note = _human_decision(item, city.city)
    commitment_id = f"commit-{uuid4().hex[:12]}"
    created_at = _now().isoformat()
    project_ids = [project.project_id for project in projects]
    amount = format(item.amount_usd, "f")
    title = item.title.strip()
    store.save_catalog_commitment(
        commitment_id,
        city.country,
        city.city,
        title,
        amount,
        project_ids,
        created_at,
        recommended,
        human_choice,
        decision_note,
    )
    return CatalogCommitment(
        commitment_id=commitment_id,
        country=city.country,
        city=city.city,
        title=title,
        amount_usd=amount,
        project_ids=project_ids,
        created_at=created_at,
        projects=projects,
        impact=funding_impact(title, city.country, city.city, amount, project_ids),
        recommended_city=recommended,
        human_choice=human_choice,
        decision_note=decision_note,
    )


@app.get("/catalog/commitment", response_model=CatalogCommitment)
def get_catalog_commitment() -> CatalogCommitment:
    """Return the newest budget directed at a World Bank city."""
    row = store.latest_catalog_commitment()
    if row is None:
        raise HTTPException(status_code=404, detail="No budget has been directed to a World Bank city yet.")
    try:
        return _commitment_from_row(row)
    except CatalogUnavailableError as error:
        raise _catalog_error(error) from error
