"""Provide deterministic, cited overlap evidence for one proposal and funded project."""

from __future__ import annotations

import calendar
import csv
import re
from datetime import date
from pathlib import Path

from pydantic import BaseModel, Field

from agent.schemas import OverlapFacts, Project, Proposal


_PROJECTS_PATH = Path(__file__).resolve().parents[2] / "data" / "processed" / "projects.csv"
_BENEFICIARY_PATTERNS: dict[str, tuple[str, ...]] = {
    "commuters": ("commuter", "passenger", "transit user"),
    "households": ("household", "resident", "community"),
    "pedestrians": ("pedestrian", "walker"),
    "students": ("student", "schoolchild"),
    "women": ("women", "woman", "female"),
    "youth": ("youth", "young people"),
    "businesses": ("business", "merchant", "market trader"),
}
_CONCRETE_OUTPUT_PATTERNS = (
    re.compile(
        r"\b\d+(?:\.\d+)?\s*(?:km|kilomet(?:er|re)s?|m|met(?:er|re)s?|"
        r"housing units?|units?|stations?|stops?|schools?|bridges?|toilets?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:brt|bus rapid transit|metro|rail|drainage|water|sewer(?:age)?|"
        r"road)\s+(?:[A-Z][\w-]*\s+){0,2}(?:line|corridor|network|system)\b",
        re.IGNORECASE,
    ),
)


class OverlapCheckInput(BaseModel):
    """Validated arguments for deterministic proposal/project overlap evidence."""

    proposal: Proposal
    project_id: str = Field(min_length=1)


class ProjectNotFoundError(LookupError):
    """Raised when a requested project ID is absent from the local source."""


def check_overlap(proposal: Proposal, project_id: str) -> OverlapFacts:
    """Compare a proposal with one funded project using only canonical IDs and local data.

    Return exact city and district equality, conservative date overlap after exactly
    twelve calendar months of slack at every known endpoint, sector evidence, and
    distinct concrete location, beneficiary, output, and period matching attributes.
    Missing locations or dates never create a positive match. Use the returned facts
    as evidence; do not infer additional geography, beneficiaries, or outputs.
    """
    validated = OverlapCheckInput(proposal=proposal, project_id=project_id)
    project = _load_project(validated.project_id)

    districts_known = (
        validated.proposal.district_id is not None and project.district is not None
    )
    same_city = validated.proposal.city_id == project.city
    same_district = districts_known and validated.proposal.district_id == project.district
    dates_known = (
        validated.proposal.start_date is not None
        and validated.proposal.end_date is not None
        and project.approval_date is not None
        and project.closing_date is not None
    )
    periods_overlap = dates_known and _periods_overlap_with_slack(
        validated.proposal.start_date,
        validated.proposal.end_date,
        project.approval_date,
        project.closing_date,
    )
    same_sector = validated.proposal.sector.casefold() == project.sector.casefold()

    proposal_text = f"{validated.proposal.title} {validated.proposal.description}"
    project_text = f"{project.name} {project.description} {project.themes}"
    proposal_beneficiaries = _beneficiaries_in(proposal_text)
    project_beneficiaries = _beneficiaries_in(project_text)
    shared_beneficiaries = _shared_beneficiaries(
        proposal_beneficiaries, project_beneficiaries
    )
    shared_outputs = _concrete_outputs_in(proposal_text) & _concrete_outputs_in(project_text)

    matching_attributes: list[str] = []
    if same_city:
        matching_attributes.append(f"city:{validated.proposal.city_id}")
    if same_district:
        matching_attributes.append(f"district:{validated.proposal.district_id}")
    if periods_overlap:
        matching_attributes.append("implementation_period:12_month_slack")
    if shared_beneficiaries:
        matching_attributes.extend(
            f"beneficiary:{beneficiary}"
            for beneficiary in sorted(proposal_beneficiaries & project_beneficiaries)
        )
    matching_attributes.extend(f"output:{output}" for output in sorted(shared_outputs))

    return OverlapFacts(
        same_city=same_city,
        same_district=same_district,
        districts_known=districts_known,
        dates_known=dates_known,
        periods_overlap_with_slack=periods_overlap,
        same_sector=same_sector,
        shared_beneficiaries=shared_beneficiaries,
        matching_attributes=matching_attributes,
        evidence_project_id=project.project_id,
    )


def _load_project(project_id: str) -> Project:
    """Load one canonical project record from the local processed source."""
    try:
        with _PROJECTS_PATH.open(newline="", encoding="utf-8") as source:
            for row in csv.DictReader(source):
                if row.get("project_id") == project_id:
                    return Project.model_validate(row)
    except OSError as error:
        raise ProjectNotFoundError(f"Local project source is unavailable: {project_id}") from error

    raise ProjectNotFoundError(f"Project not found: {project_id}")


def _periods_overlap_with_slack(
    proposal_start: date | None,
    proposal_end: date | None,
    project_start: date | None,
    project_end: date | None,
) -> bool:
    """Return inclusive overlap after extending each complete interval by 12 months."""
    if None in (proposal_start, proposal_end, project_start, project_end):
        return False

    assert proposal_start is not None
    assert proposal_end is not None
    assert project_start is not None
    assert project_end is not None
    return (
        _add_calendar_months(proposal_start, -12)
        <= _add_calendar_months(project_end, 12)
        and _add_calendar_months(project_start, -12)
        <= _add_calendar_months(proposal_end, 12)
    )


def _add_calendar_months(value: date, months: int) -> date:
    """Shift a date by calendar months while retaining the nearest valid day."""
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _beneficiaries_in(text: str) -> set[str]:
    """Extract explicit beneficiary categories from source text without inference."""
    lowered = text.casefold()
    return {
        category
        for category, terms in _BENEFICIARY_PATTERNS.items()
        if any(term in lowered for term in terms)
    }


def _shared_beneficiaries(
    proposal_beneficiaries: set[str], project_beneficiaries: set[str]
) -> bool | None:
    """Return unknown unless both records contain explicit beneficiary evidence."""
    if not proposal_beneficiaries or not project_beneficiaries:
        return None
    return bool(proposal_beneficiaries & project_beneficiaries)


def _concrete_outputs_in(text: str) -> set[str]:
    """Extract explicitly named or quantified infrastructure outputs from text."""
    return {
        re.sub(r"\s+", " ", match.group(0).casefold()).strip()
        for pattern in _CONCRETE_OUTPUT_PATTERNS
        for match in pattern.finditer(text)
    }
