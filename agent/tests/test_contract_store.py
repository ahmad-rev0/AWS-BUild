"""Focused contract and SQLite store tests for clash-review records."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from agent.schemas import (
    Approval,
    AuditEvent,
    ClashReport,
    Memo,
    Proposal,
    ProposalCreate,
    ProposalStatus,
    Recommendation,
    Role,
    Verdict,
    VerdictLabel,
)
from agent.store import SQLiteStore, StoreConflictError


NOW = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)


def proposal() -> Proposal:
    """Build one valid persisted proposal with stable IDs."""
    return Proposal(
        proposal_id="proposal-01",
        title="North corridor drainage",
        description="Build drainage channels for flood-prone streets.",
        city_id="city-01",
        district_id="district-01",
        sector="water",
        budget_usd=Decimal("1200000"),
        start_date=date(2026, 2, 1),
        end_date=date(2027, 2, 1),
        source="seeded",
        submitted_at=NOW,
    )


def audit(event_id: str, event_type: str, **values: str) -> AuditEvent:
    """Build a complete audit row with an explicit non-secret summary."""
    return AuditEvent(
        event_id=event_id,
        event_type=event_type,
        timestamp=NOW,
        payload_summary="Lifecycle event recorded.",
        **values,
    )


def report() -> ClashReport:
    """Build the validated report used to complete a stored review."""
    return ClashReport(
        proposal_id="proposal-01",
        candidates=[
            Verdict(
                project_id="project-01",
                label=VerdictLabel.OVERLAPPING,
                confidence=0.8,
                matching_attributes=["district-01", "drainage channels"],
                reasoning="The projects serve the same flood-prone streets.",
            )
        ],
        memo=Memo(
            recommendation=Recommendation.CO_FINANCE,
            summary="Coordinate procurement for compatible drainage work.",
        ),
        model_id="cached-contract-test",
        latency_ms=0,
        source="seeded",
    )


@pytest.fixture
def store(tmp_path: pytest.TempPathFactory) -> SQLiteStore:
    """Return an initialized isolated SQLite store."""
    return SQLiteStore(tmp_path / "atlas11.db")


def create_submitted_proposal(store: SQLiteStore) -> Proposal:
    """Persist the common submitted proposal and its required intake audit."""
    item = proposal()
    return store.create_proposal(
        item,
        audit(
            "audit-intake-01",
            "proposal_intake",
            proposal_id=item.proposal_id,
            actor="planner-01",
            role=Role.PLANNER,
        ),
    )


def create_pending_review(store: SQLiteStore) -> None:
    """Create the pending review required before review completion."""
    store.create_review(
        "review-01",
        "proposal-01",
        "seeded",
        NOW.isoformat(),
        audit(
            "audit-review-created-01",
            "review_created",
            proposal_id="proposal-01",
            review_id="review-01",
        ),
    )


def test_contracts_reject_invalid_dates_and_preserve_seeded_source() -> None:
    """Proposal intake contracts reject reversed dates and retain seeded provenance."""
    with pytest.raises(ValidationError, match="end_date must not precede start_date"):
        ProposalCreate(
            title="Invalid dates",
            description="This proposal uses an invalid implementation window.",
            city_id="city-01",
            sector="transport",
            budget_usd=Decimal("0"),
            start_date=date(2026, 2, 1),
            end_date=date(2026, 1, 31),
        )

    valid = ProposalCreate(
        title="Seeded proposal",
        description="A deterministic offline scenario.",
        city_id="city-01",
        sector="transport",
        budget_usd=Decimal("0"),
        source="seeded",
    )

    assert valid.source == "seeded"


def test_create_proposal_persists_submitted_record_and_intake_audit(store: SQLiteStore) -> None:
    """Proposal insertion retains canonical fields, status, provenance, and audit data."""
    inserted = create_submitted_proposal(store)

    assert inserted.status is ProposalStatus.SUBMITTED
    assert store.get_proposal("proposal-01") == inserted
    events = store.list_audit(proposal_id="proposal-01")
    assert [(event.event_type, event.actor, event.role) for event in events] == [
        ("proposal_intake", "planner-01", Role.PLANNER)
    ]


def test_complete_review_rolls_back_report_and_status_when_audit_insert_fails(
    store: SQLiteStore,
) -> None:
    """A failed completion audit leaves the report and proposal transition uncommitted."""
    create_submitted_proposal(store)
    create_pending_review(store)
    store.append_audit(
        audit(
            "audit-report-completed-01",
            "preexisting_event",
            proposal_id="proposal-01",
            review_id="review-01",
        )
    )

    with pytest.raises(StoreConflictError, match="Audit event already exists"):
        store.complete_review(
            "review-01",
            report(),
            NOW.isoformat(),
            [
                audit(
                    "audit-report-completed-01",
                    "report_completed",
                    proposal_id="proposal-01",
                    review_id="review-01",
                )
            ],
        )

    assert store.get_proposal("proposal-01").status is ProposalStatus.SUBMITTED
    with pytest.raises(StoreConflictError, match="Review is not complete"):
        store.get_completed_report("review-01")


def test_record_approval_persists_terminal_decision_and_audit(store: SQLiteStore) -> None:
    """An approver decision is stored with the terminal proposal transition and audit row."""
    create_submitted_proposal(store)
    create_pending_review(store)
    store.complete_review(
        "review-01",
        report(),
        NOW.isoformat(),
        [
            audit(
                "audit-report-completed-01",
                "report_completed",
                proposal_id="proposal-01",
                review_id="review-01",
            )
        ],
    )
    approval = Approval(
        approval_id="approval-01",
        review_id="review-01",
        proposal_id="proposal-01",
        actor="approver-01",
        role=Role.APPROVER,
        decision="APPROVED",
        decided_at=NOW,
    )

    assert store.record_approval(
        approval,
        Role.APPROVER,
        audit(
            "audit-approval-01",
            "approval_accepted",
            proposal_id="proposal-01",
            review_id="review-01",
            approval_id="approval-01",
            actor="approver-01",
            role=Role.APPROVER,
        ),
    ) == approval
    assert store.get_proposal("proposal-01").status is ProposalStatus.APPROVED
    approval_events = store.list_audit(proposal_id="proposal-01", review_id="review-01")
    assert any(
        event.approval_id == "approval-01"
        and event.actor == "approver-01"
        and event.role is Role.APPROVER
        for event in approval_events
    )


def test_list_audit_returns_sanitized_rows_with_required_identifiers(store: SQLiteStore) -> None:
    """Audit reads redact secret-like values while retaining durable trace identifiers."""
    store.append_audit(
        AuditEvent(
            event_id="audit-sanitized-01",
            event_type="tool_failure",
            timestamp=NOW,
            proposal_id="proposal-01",
            review_id="review-01",
            actor="planner-01",
            role=Role.PLANNER,
            payload_summary="AWS_SESSION_TOKEN=unsafe-value password=also-unsafe tool failed.",
        )
    )

    [event] = store.list_audit(proposal_id="proposal-01", review_id="review-01")
    assert event.event_type == "tool_failure"
    assert event.timestamp == NOW
    assert event.actor == "planner-01"
    assert event.role is Role.PLANNER
    assert "unsafe-value" not in event.payload_summary
    assert "also-unsafe" not in event.payload_summary
    assert event.payload_summary.count("[REDACTED]") == 2
