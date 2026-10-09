"""Shared Pydantic contracts for Atlas11 pipeline and clash-review data."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
import math
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


CANONICAL_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
SOURCE_LABELS = frozenset({"worldbank_api", "iati", "seeded", "user", "live"})


class CanonicalContract(BaseModel):
    """Base contract that preserves canonical identifiers and source labels verbatim."""

    @model_validator(mode="before")
    @classmethod
    def validate_canonical_values(cls, values: object) -> object:
        """Reject non-canonical IDs and source labels instead of normalizing them."""
        if not isinstance(values, dict):
            return values

        for field_name, value in values.items():
            if field_name.endswith("_id") and value is not None:
                if not isinstance(value, str) or not CANONICAL_ID_PATTERN.fullmatch(
                    value
                ):
                    raise ValueError(f"{field_name} must be a stable canonical ID")
            if field_name == "source" and value is not None:
                if not isinstance(value, str) or value not in SOURCE_LABELS:
                    raise ValueError("source must be a stable supported source label")
        return values


class Project(CanonicalContract):
    """A normalized existing urban development project with source provenance."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    project_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    funder: str = Field(min_length=1)
    country: str = Field(min_length=1)
    city: str | None = None
    district: str | None = None
    sector: str = Field(min_length=1)
    themes: str = ""
    description: str = ""
    amount_usd: Decimal = Field(ge=0, allow_inf_nan=False)
    approval_date: date | None = None
    closing_date: date | None = None
    status: str | None = None
    is_urban: bool = True
    source: Literal["worldbank_api", "iati", "seeded"]
    source_url: str | None = None

    @field_validator(
        "city",
        "district",
        "approval_date",
        "closing_date",
        "status",
        "source_url",
        mode="before",
    )
    @classmethod
    def empty_optional_values_are_none(cls, value: object) -> object:
        """Normalize empty CSV cells and string nulls to missing optional values."""
        if isinstance(value, str) and value.strip().lower() in {"", "none", "null"}:
            return None
        return value

    @field_validator("approval_date", "closing_date", mode="before")
    @classmethod
    def parse_world_bank_dates(cls, value: object) -> object:
        """Accept ISO dates and known World Bank timestamp forms from normalized CSVs."""
        if not isinstance(value, str):
            return value
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            return date.fromisoformat(cleaned)
        except ValueError:
            pass
        for date_format in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y"):
            try:
                return datetime.strptime(cleaned, date_format).date()
            except ValueError:
                continue
        return value

    @model_validator(mode="after")
    def validate_dates_and_provenance(self) -> "Project":
        """Enforce date ordering and provenance URL requirements."""
        if (
            self.approval_date is not None
            and self.closing_date is not None
            and self.closing_date < self.approval_date
        ):
            raise ValueError("closing_date must not precede approval_date")
        if self.source in {"worldbank_api", "iati"} and not self.source_url:
            raise ValueError("source_url is required for fetched project sources")
        return self


class Candidate(CanonicalContract):
    """A normalized project similarity result returned by retrieval."""

    project_id: str = Field(min_length=1)
    score: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)


class RejectedRow(BaseModel):
    """A CSV row excluded from indexing, with a location and reason."""

    file: str = Field(min_length=1)
    row_number: int = Field(gt=0)
    project_id: str | None = None
    reason: str = Field(min_length=1)


class IndexReport(BaseModel):
    """Summary of one complete or incremental project-indexing operation."""

    provider: str = Field(min_length=1)
    indexed: int = Field(ge=0)
    skipped_unchanged: int = Field(ge=0)
    rejected: list[RejectedRow] = Field(default_factory=list)
    collection: str = "projects"


class ProposalStatus(StrEnum):
    """Lifecycle states for a submitted coordination proposal."""

    SUBMITTED = "SUBMITTED"
    REVIEWED = "REVIEWED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class VerdictLabel(StrEnum):
    """Closed clash taxonomy used for a proposal/project pair."""

    DUPLICATE = "DUPLICATE"
    OVERLAPPING = "OVERLAPPING"
    COMPLEMENTARY = "COMPLEMENTARY"
    UNRELATED = "UNRELATED"


class Recommendation(StrEnum):
    """Coordination actions that a review memo may recommend."""

    MERGE = "MERGE"
    CO_FINANCE = "CO_FINANCE"
    PROCEED = "PROCEED"
    REDIRECT = "REDIRECT"


class Role(StrEnum):
    """Supported actor roles at the coordination API boundary."""

    PLANNER = "planner"
    APPROVER = "approver"


class ProposalCreate(CanonicalContract):
    """Validated payload accepted when a planner submits a proposal."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=10_000)
    city_id: str = Field(min_length=1)
    district_id: str | None = None
    sector: str = Field(min_length=1)
    budget_usd: Decimal = Field(ge=0)
    start_date: date | None = None
    end_date: date | None = None
    scenario_key: str | None = None
    source: Literal["seeded", "user"] = "user"

    @model_validator(mode="after")
    def dates_are_ordered(self) -> "ProposalCreate":
        """Reject an implementation end date before its start date."""
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("end_date must not precede start_date")
        return self


class Proposal(ProposalCreate):
    """Persisted proposal shared by review, storage, and API layers."""

    proposal_id: str = Field(min_length=1)
    status: ProposalStatus = ProposalStatus.SUBMITTED
    submitted_at: datetime


class ReviewCreated(CanonicalContract):
    """Acknowledgement returned when a review is created."""

    review_id: str = Field(min_length=1)


class Verdict(CanonicalContract):
    """Validated classification and rationale for one cited project."""

    model_config = ConfigDict(str_strip_whitespace=True)

    project_id: str = Field(min_length=1)
    label: VerdictLabel
    confidence: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    matching_attributes: list[str] = Field(default_factory=list)
    reasoning: str = Field(min_length=1)

    @field_validator("confidence")
    @classmethod
    def confidence_is_finite(cls, value: float) -> float:
        """Require externally returned confidence to be finite and bounded."""
        if not math.isfinite(value):
            raise ValueError("confidence must be finite")
        return value


class Memo(CanonicalContract):
    """Structured coordination recommendation derived from validated verdicts."""

    model_config = ConfigDict(str_strip_whitespace=True)

    recommendation: Recommendation
    summary: str = Field(min_length=1)
    redirect_district_id: str | None = None

    @model_validator(mode="after")
    def redirect_has_redirect_recommendation(self) -> "Memo":
        """Allow a redirect district only when redirecting coordination focus."""
        if (
            self.redirect_district_id is not None
            and self.recommendation is not Recommendation.REDIRECT
        ):
            raise ValueError(
                "redirect_district_id is only allowed for REDIRECT recommendations"
            )
        return self


class ClashReport(CanonicalContract):
    """Schema-validated final output from a live or cached clash review."""

    proposal_id: str = Field(min_length=1)
    candidates: list[Verdict]
    memo: Memo
    model_id: str = Field(min_length=1)
    latency_ms: int = Field(ge=0)
    source: Literal["live", "seeded"]


class ApprovalCreate(CanonicalContract):
    """Request for an approver to make a terminal coordination decision."""

    model_config = ConfigDict(str_strip_whitespace=True)

    review_id: str = Field(min_length=1)
    decision: Literal["APPROVED", "REJECTED"]
    actor: str = Field(min_length=1)
    role: Role
    reason: str | None = None

    @model_validator(mode="after")
    def rejection_requires_reason(self) -> "ApprovalCreate":
        """Require a non-empty reason for a requested rejection."""
        if self.decision == "REJECTED" and not self.reason:
            raise ValueError("reason is required when decision is REJECTED")
        return self


class Approval(CanonicalContract):
    """Persisted human coordination sign-off; it never represents funding."""

    approval_id: str = Field(min_length=1)
    review_id: str = Field(min_length=1)
    proposal_id: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    role: Role
    decision: Literal["APPROVED", "REJECTED"]
    decided_at: datetime
    reason: str | None = None

    @model_validator(mode="after")
    def rejection_requires_reason(self) -> "Approval":
        """Prevent persisted rejections without an explanatory reason."""
        if self.decision == "REJECTED" and not self.reason:
            raise ValueError("reason is required when decision is REJECTED")
        return self


class SseEvent(BaseModel):
    """JSON payload transported in a review server-sent event."""

    type: Literal["status", "tool_call", "verdict", "done", "error"]
    name: str | None = None
    ms: int | None = Field(default=None, ge=0)
    payload: dict[str, object] | None = None


class OverlapFacts(CanonicalContract):
    """Deterministic location, period, and evidence facts for a project pair."""

    same_city: bool
    same_district: bool
    districts_known: bool
    dates_known: bool
    periods_overlap_with_slack: bool
    same_sector: bool
    shared_beneficiaries: bool | None
    matching_attributes: list[str] = Field(default_factory=list)
    evidence_project_id: str = Field(min_length=1)


class AuditEvent(CanonicalContract):
    """Sanitized immutable record of a lifecycle or decision event."""

    event_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    timestamp: datetime
    proposal_id: str | None = None
    review_id: str | None = None
    project_id: str | None = None
    approval_id: str | None = None
    actor: str | None = None
    role: Role | None = None
    payload_summary: str = Field(min_length=1)
