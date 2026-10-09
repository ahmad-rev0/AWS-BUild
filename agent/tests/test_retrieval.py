"""Offline unit tests for validated Chroma retrieval behavior."""

from datetime import date
import math

import pytest
from hypothesis import given, strategies as st

from agent.errors import SearchInputError
from agent import retrieval


class FakeProvider:
    """Deterministic provider avoiding model loads and network calls."""

    def embed_query(self, text: str) -> list[float]:
        return [0.1, 0.2]


class FakeCollection:
    """A minimal in-memory Chroma query result source."""

    def count(self) -> int:
        return 4

    def query(self, **_: object) -> dict[str, list[list[object]]]:
        return {
            "ids": [["P-2", "P-1", "P-1", "P-3"]],
            "distances": [[0.2, 0.2, 0.8, float("nan")]],
            "metadatas": [
                [
                    {
                        "city": "Karachi",
                        "district": "D-1",
                        "approval_date": "2024-01-01",
                        "closing_date": "2025-01-01",
                    },
                    {
                        "city": "Karachi",
                        "district": "D-1",
                        "approval_date": "2024-01-01",
                        "closing_date": "2025-01-01",
                    },
                    {
                        "city": "Karachi",
                        "district": "D-1",
                        "approval_date": "2024-01-01",
                        "closing_date": "2025-01-01",
                    },
                    {
                        "city": "Lahore",
                        "district": "D-2",
                        "approval_date": "",
                        "closing_date": "",
                    },
                ]
            ],
        }


def _fake_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        retrieval, "create_embedding_provider", lambda _: FakeProvider()
    )
    monkeypatch.setattr(retrieval, "_collection", lambda _: FakeCollection())


def test_search_deduplicates_normalizes_and_exactly_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_dependencies(monkeypatch)

    candidates = retrieval.search(
        "drainage", filters={"city": "Karachi", "district": "D-1"}
    )

    assert [(candidate.project_id, candidate.score) for candidate in candidates] == [
        ("P-1", 0.8),
        ("P-2", 0.8),
    ]


def test_date_window_is_inclusive_and_excludes_unknown_dates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_dependencies(monkeypatch)

    candidates = retrieval.search(
        "drainage",
        filters={
            "approval_date_from": date(2025, 1, 1),
            "closing_date_to": date(2025, 1, 1),
        },
    )

    assert {candidate.project_id for candidate in candidates} == {"P-1", "P-2"}


@pytest.mark.parametrize(
    ("text", "k", "filters"),
    [
        (" ", 1, None),
        ("query", 0, None),
        ("query", True, None),
        ("query", 101, None),
        ("query", 1, {"unknown": "x"}),
        ("query", 1, {"approval_date_from": "2024-13-01"}),
        (
            "query",
            1,
            {"approval_date_from": "2025-01-02", "approval_date_to": "2025-01-01"},
        ),
    ],
)
def test_invalid_input_fails_before_provider_or_chroma(
    monkeypatch: pytest.MonkeyPatch, text: str, k: int, filters: object
) -> None:
    monkeypatch.setattr(
        retrieval, "create_embedding_provider", lambda _: pytest.fail("queried")
    )
    with pytest.raises(SearchInputError):
        retrieval.search(text, k=k, filters=filters)  # type: ignore[arg-type]


@given(st.floats(allow_nan=True, allow_infinity=True, width=64))
def test_normalized_distances_are_finite_and_bounded(distance: float) -> None:
    score = retrieval.normalize_distance(distance)
    assert math.isfinite(score)
    assert 0.0 <= score <= 1.0
    if not math.isfinite(distance):
        assert score == 0.0
