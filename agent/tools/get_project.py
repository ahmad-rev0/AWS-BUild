"""Load one canonical funded-project record from the local normalized source."""

from __future__ import annotations

import csv
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from agent.errors import ProjectNotFoundError
from agent.schemas import CanonicalContract, Project

PROJECT_SOURCE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "processed" / "projects.csv"
)


class GetProjectInput(CanonicalContract):
    """Validated canonical project identifier accepted by the project lookup tool."""

    model_config = ConfigDict(str_strip_whitespace=True)

    project_id: str = Field(min_length=1)


class GetProjectOutput(BaseModel):
    """Canonical project record, including its preserved source provenance."""

    project: Project


def get_project(project_id: str) -> GetProjectOutput:
    """Return the exact local funded-project record for a canonical project ID.

    Use this after candidate retrieval to inspect authoritative project details and
    provenance. Supply only a stable project ID. The tool never invents a project:
    an absent ID raises a typed not-found failure.
    """

    lookup = GetProjectInput.model_validate({"project_id": project_id})
    return GetProjectOutput(project=_load_project(lookup.project_id))


def _load_project(project_id: str, source_path: Path | None = None) -> Project:
    """Load an exact canonical project match from the normalized local CSV source."""

    resolved_source_path = source_path or PROJECT_SOURCE_PATH
    try:
        with resolved_source_path.open(newline="", encoding="utf-8") as project_file:
            for row in csv.DictReader(project_file):
                if row.get("project_id") == project_id:
                    return Project.model_validate(row)
    except OSError as error:
        raise ProjectNotFoundError(project_id) from error

    raise ProjectNotFoundError(project_id)
