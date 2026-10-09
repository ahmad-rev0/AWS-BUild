"""Build Atlas11's persistent local Chroma project index from normalized CSV inputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.config import PipelineConfig
from agent.embeddings import EmbeddingProvider, create_embedding_provider
from agent.errors import EmbeddingProviderError, MissingDataError
from agent.schemas import IndexReport, Project, RejectedRow

MANIFEST_NAME = "index_manifest.json"


def canonical_embedding_text(project: Project) -> str:
    """Return stable normalized text for the three fields used in every embedding."""
    return "\n".join(
        value.strip() for value in (project.name, project.description, project.themes)
    )


def content_hash(project: Project) -> str:
    """Hash all normalized project fields deterministically, including metadata."""
    payload = json.dumps(
        project.model_dump(mode="json", exclude_none=False),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _reject(
    path: Path, row_number: int, row: dict[str, str], reason: str
) -> RejectedRow:
    return RejectedRow(
        file=str(path),
        row_number=row_number,
        project_id=row.get("project_id") or None,
        reason=reason,
    )


def load_projects(
    projects_path: Path, seeded_path: Path
) -> tuple[list[Project], list[RejectedRow]]:
    """Load independent CSV rows, enforcing file-specific provenance and duplicate rejection."""
    if not projects_path.is_file():
        raise MissingDataError(
            f"Missing required {projects_path}. Run the worldbank-ingest skill before building the index."
        )

    accepted: list[tuple[Project, Path, int, dict[str, str]]] = []
    rejected: list[RejectedRow] = []
    for path, seeded_file in ((projects_path, False), (seeded_path, True)):
        if seeded_file and not path.is_file():
            continue
        with path.open(newline="", encoding="utf-8") as source:
            for row_number, row in enumerate(csv.DictReader(source), start=2):
                project_id = row.get("project_id") or None
                source_value = (row.get("source") or "").strip()
                if seeded_file and source_value != "seeded":
                    rejected.append(
                        _reject(
                            path, row_number, row, "seeded input requires source=seeded"
                        )
                    )
                    continue
                if not seeded_file and source_value == "seeded":
                    rejected.append(
                        _reject(
                            path,
                            row_number,
                            row,
                            "primary input must not contain source=seeded",
                        )
                    )
                    continue
                try:
                    accepted.append(
                        (Project.model_validate(row), path, row_number, row)
                    )
                except ValidationError as error:
                    rejected.append(_reject(path, row_number, row, str(error)))

    duplicate_ids = {
        project.project_id
        for project, _, _, _ in accepted
        if project.project_id
        and sum(item[0].project_id == project.project_id for item in accepted) > 1
    }
    projects: list[Project] = []
    for project, path, row_number, row in accepted:
        if project.project_id in duplicate_ids:
            rejected.append(
                _reject(
                    path, row_number, row, "duplicate project_id across index inputs"
                )
            )
        else:
            projects.append(project)
    return projects, rejected


def _manifest_path(index_path: Path) -> Path:
    return index_path / MANIFEST_NAME


def _read_manifest(index_path: Path) -> dict[str, Any]:
    path = _manifest_path(index_path)
    if not path.is_file():
        return {"projects": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        projects = data.get("projects")
        if not isinstance(projects, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in projects.items()
        ):
            raise ValueError("projects must be a string-to-hash object")
        return data
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise MissingDataError(f"Invalid index manifest at {path}: {error}") from error


def _write_manifest(
    index_path: Path, projects: dict[str, str], provider: EmbeddingProvider
) -> None:
    index_path.mkdir(parents=True, exist_ok=True)
    target = _manifest_path(index_path)
    payload = {
        "projects": projects,
        "provider": provider.name,
        "model_id": provider.model_id,
    }
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=index_path, delete=False
    ) as staged:
        json.dump(payload, staged, sort_keys=True, separators=(",", ":"))
        staged.flush()
        os.fsync(staged.fileno())
        staged_path = Path(staged.name)
    try:
        staged_path.replace(target)
    except OSError:
        staged_path.unlink(missing_ok=True)
        raise


def _collection(index_path: Path, name: str) -> Any:
    try:
        import chromadb

        return chromadb.PersistentClient(path=str(index_path)).get_or_create_collection(
            name=name, metadata={"hnsw:space": "cosine"}
        )
    except Exception as error:
        raise EmbeddingProviderError(
            "Unable to open persistent local Chroma index."
        ) from error


def _metadata(project: Project) -> dict[str, str | float]:
    return {
        "city": project.city or "",
        "district": project.district or "",
        "sector": project.sector,
        "funder": project.funder,
        "approval_date": project.approval_date.isoformat()
        if project.approval_date
        else "",
        "closing_date": project.closing_date.isoformat()
        if project.closing_date
        else "",
        "amount_usd": float(project.amount_usd),
        "source": project.source,
        "content_hash": content_hash(project),
    }


def build_index(
    *, root: Path, provider: EmbeddingProvider, incremental: bool = False
) -> IndexReport:
    """Validate inputs and commit a full or incremental persistent Chroma reconciliation."""
    config = PipelineConfig.from_environment(root)
    projects, rejected = load_projects(
        root / "data" / "processed" / "projects.csv",
        root / "data" / "processed" / "seeded_projects.csv",
    )
    if not projects:
        raise MissingDataError(
            "No valid project rows were available; existing index was left unchanged."
        )

    old_manifest = (
        _read_manifest(config.chroma_path) if incremental else {"projects": {}}
    )
    old_hashes = old_manifest["projects"]
    current_hashes = {project.project_id: content_hash(project) for project in projects}
    changed = [
        project
        for project in projects
        if not incremental
        or old_hashes.get(project.project_id) != current_hashes[project.project_id]
    ]
    vectors = provider.embed_documents(
        [canonical_embedding_text(project) for project in changed]
    )
    if len(vectors) != len(changed) or any(not vector for vector in vectors):
        raise EmbeddingProviderError(
            "Embedding failed: provider returned malformed vector output."
        )

    collection = _collection(config.chroma_path, config.chroma_collection)
    stale_ids = sorted(set(old_hashes) - set(current_hashes)) if incremental else []
    try:
        if changed:
            collection.upsert(
                ids=[project.project_id for project in changed],
                embeddings=vectors,
                documents=[canonical_embedding_text(project) for project in changed],
                metadatas=[_metadata(project) for project in changed],
            )
        if stale_ids:
            collection.delete(ids=stale_ids)
        _write_manifest(config.chroma_path, current_hashes, provider)
    except Exception as error:
        raise EmbeddingProviderError(
            "Indexing failed; the previous committed manifest was preserved."
        ) from error
    return IndexReport(
        provider=provider.name,
        indexed=len(changed),
        skipped_unchanged=len(projects) - len(changed),
        rejected=rejected,
        collection=config.chroma_collection,
    )


def main() -> int:
    """Run the indexer and print a concise machine-readable report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--incremental", action="store_true")
    args = parser.parse_args()
    try:
        config = PipelineConfig.from_environment(ROOT)
        report = build_index(
            root=ROOT,
            provider=create_embedding_provider(config),
            incremental=args.incremental,
        )
        print(report.model_dump_json())
        return 0
    except (MissingDataError, EmbeddingProviderError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
