"""Offline tests for CSV loading and incremental index reconciliation."""

import json
from pathlib import Path

import pytest

from agent.errors import MissingDataError
from scripts import build_index


HEADER = "project_id,name,funder,country,city,district,sector,themes,description,amount_usd,approval_date,closing_date,status,is_urban,source,source_url\n"
ROW = "P-1,Drainage,World Bank,Pakistan,Karachi,D-1,Water,Resilience,Drainage upgrade,1000,2024-01-01,2025-01-01,Active,true,worldbank_api,https://example.test/P-1\n"


class FakeProvider:
    """Record document calls without invoking an embedding runtime."""

    name = "fake"
    model_id = "fake-v1"

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[0.1, 0.2] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.1, 0.2]


class FakeCollection:
    """Capture persistent collection mutations for deterministic verification."""

    def __init__(self) -> None:
        self.upserts: list[list[str]] = []
        self.deleted: list[list[str]] = []

    def upsert(self, *, ids: list[str], **_: object) -> None:
        self.upserts.append(ids)

    def delete(self, *, ids: list[str]) -> None:
        self.deleted.append(ids)


def _root(tmp_path: Path) -> Path:
    (tmp_path / "data" / "processed").mkdir(parents=True)
    (tmp_path / "data" / "processed" / "projects.csv").write_text(
        HEADER + ROW, encoding="utf-8"
    )
    return tmp_path


def test_load_projects_rejects_seeded_primary_and_duplicate_ids(tmp_path: Path) -> None:
    root = _root(tmp_path)
    primary = root / "data" / "processed" / "projects.csv"
    seeded = root / "data" / "processed" / "seeded_projects.csv"
    seeded.write_text(
        HEADER
        + ROW.replace("worldbank_api", "seeded").replace(
            "https://example.test/P-1", ""
        ),
        encoding="utf-8",
    )
    primary.write_text(
        HEADER + ROW + ROW.replace("P-1", "P-2").replace("worldbank_api", "seeded"),
        encoding="utf-8",
    )

    projects, rejected = build_index.load_projects(primary, seeded)

    assert projects == []
    assert len(rejected) == 3
    assert {item.row_number for item in rejected} == {2, 3}


def test_missing_primary_has_actionable_ingest_error(tmp_path: Path) -> None:
    with pytest.raises(MissingDataError, match="worldbank-ingest"):
        build_index.load_projects(
            tmp_path / "projects.csv", tmp_path / "seeded_projects.csv"
        )


def test_incremental_skips_unchanged_and_deletes_stale(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _root(tmp_path)
    collection = FakeCollection()
    provider = FakeProvider()
    monkeypatch.setenv("CHROMA_PATH", str(root / "data" / "index"))
    monkeypatch.setattr(build_index, "_collection", lambda *_: collection)

    first = build_index.build_index(root=root, provider=provider)
    second = build_index.build_index(root=root, provider=provider, incremental=True)
    manifest = json.loads((root / "data" / "index" / "index_manifest.json").read_text())

    assert first.indexed == 1
    assert second.indexed == 0
    assert second.skipped_unchanged == 1
    assert len(provider.calls) == 2
    assert provider.calls[-1] == []
    assert manifest["projects"]
    assert collection.upserts == [["P-1"]]


def test_canonical_content_hash_tracks_metadata_changes() -> None:
    project = build_index.Project.model_validate(
        {
            "project_id": "P-1",
            "name": "Name",
            "funder": "Funder",
            "country": "Country",
            "sector": "Water",
            "amount_usd": "1",
            "source": "seeded",
        }
    )
    modified = project.model_copy(update={"city": "Karachi"})

    assert build_index.canonical_embedding_text(project) == "Name\n\n"
    assert build_index.content_hash(project) != build_index.content_hash(modified)
