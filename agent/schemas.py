"""Shared Pydantic contracts for Atlas11 project and pipeline data."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Project(BaseModel):
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


class Candidate(BaseModel):
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
