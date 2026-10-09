"""Focused tests for the canonical local project lookup tool."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest
from hypothesis import given, strategies as st
from pydantic import ValidationError

from agent.errors import ProjectNotFoundError
from agent.tools import get_project as project_tool
from agent.tools.get_project import GetProjectOutput


FIXTURE_PROJECTS = """project_id,name,funder,country,city,district,sector,themes,description,amount_usd,approval_date,closing_date,status,is_urban,source,source_url
P-001,Drainage Upgrade,World Bank,Pakistan,Karachi,D-01,Water,Resilience,Upgrade drainage,1000,2024-01-01,2025-01-01,Active,true,worldbank_api,https://example.test/P-001
"""


def test_get_project_returns_exact_canonical_record_and_provenance(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source_path = tmp_path / "projects.csv"
    source_path.write_text(FIXTURE_PROJECTS, encoding="utf-8")
    monkeypatch.setattr(project_tool, "PROJECT_SOURCE_PATH", source_path)

    result = project_tool.get_project("P-001")

    assert isinstance(result, GetProjectOutput)
    assert result.project.project_id == "P-001"
    assert result.project.source == "worldbank_api"
    assert result.project.source_url == "https://example.test/P-001"


def test_get_project_rejects_invalid_or_absent_ids(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source_path = tmp_path / "projects.csv"
    source_path.write_text(FIXTURE_PROJECTS, encoding="utf-8")
    monkeypatch.setattr(project_tool, "PROJECT_SOURCE_PATH", source_path)

    with pytest.raises(ValidationError):
        project_tool.get_project("not a canonical id")
    with pytest.raises(ProjectNotFoundError, match="P-404"):
        project_tool.get_project("P-404")


@given(
    st.from_regex(r"P-[0-9]{3}", fullmatch=True).filter(
        lambda project_id: project_id != "P-001"
    )
)
def test_get_project_never_fabricates_a_missing_canonical_project(
    project_id: str,
) -> None:
    """Validates: Requirements 3.5."""
    with TemporaryDirectory() as directory:
        source_path = Path(directory) / "projects.csv"
        source_path.write_text(FIXTURE_PROJECTS, encoding="utf-8")
        with patch.object(project_tool, "PROJECT_SOURCE_PATH", source_path):
            with pytest.raises(ProjectNotFoundError):
                project_tool.get_project(project_id)
