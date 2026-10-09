"""Focused offline tests for golden-pair evaluation."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from agent import eval as golden_eval


def _pair(pair_id: str, expected: str, **overrides: object) -> dict[str, object]:
    """Create one provenance-labelled pair backed by an inline seeded candidate."""
    proposal = {
        "title": "Karachi Mobility Project",
        "description": "Deliver the Karachi Mobility Project for commuters.",
        "city_id": "Karachi",
        "district_id": None,
        "sector": "Urban Transport",
        "budget_usd": 100,
        "start_date": "2025-01-01",
        "end_date": "2026-01-01",
        "source": "seeded",
    }
    candidate = {
        "project_id": f"seed-{pair_id}",
        "name": "Karachi Mobility Project",
        "funder": "Test Funder",
        "country": "Testland",
        "city": "Karachi",
        "district": None,
        "sector": "Urban Transport",
        "amount_usd": 100,
        "approval_date": "2024-01-01",
        "closing_date": "2025-12-31",
        "is_urban": True,
        "source": "seeded",
    }
    proposal.update(overrides.pop("proposal", {}))  # type: ignore[arg-type]
    candidate.update(overrides.pop("candidate", {}))  # type: ignore[arg-type]
    return {
        "pair_id": pair_id,
        "proposal": proposal,
        "project_id": candidate["project_id"],
        "expected": expected,
        "rationale": "Human-reviewed deterministic fixture.",
        "labelled_by": "team",
        "source": "seeded",
        "candidate": candidate,
        **overrides,
    }


def _write_pairs(path: Path, pairs: list[dict[str, object]]) -> None:
    """Write JSON-lines fixtures in declared evaluation order."""
    path.write_text(
        "\n".join(json.dumps(pair) for pair in pairs) + "\n", encoding="utf-8"
    )


def test_quick_uses_first_six_and_full_uses_all_pairs(tmp_path: Path) -> None:
    """Quick mode is bounded while full mode retains every valid case."""
    golden = tmp_path / "golden.jsonl"
    prompt = tmp_path / "prompt.md"
    prompt.write_text("prompt", encoding="utf-8")
    pairs = [
        _pair("gp-001", "DUPLICATE"),
        _pair(
            "gp-002",
            "OVERLAPPING",
            proposal={
                "title": "Urban transit extension",
                "description": "Extend urban transit service.",
            },
        ),
        _pair(
            "gp-003",
            "COMPLEMENTARY",
            proposal={"start_date": "2028-01-01", "end_date": "2029-01-01"},
        ),
        _pair(
            "gp-004", "UNRELATED", proposal={"city_id": "Lahore"}, hard_negative=True
        ),
        _pair("gp-005", "DUPLICATE"),
        _pair(
            "gp-006",
            "OVERLAPPING",
            proposal={
                "title": "Urban transit extension",
                "description": "Extend urban transit service.",
            },
        ),
        _pair("gp-007", "UNRELATED", proposal={"city_id": "Lahore"}),
    ]
    _write_pairs(golden, pairs)

    quick = golden_eval.evaluate(golden, prompt, quick=True)
    full = golden_eval.evaluate(golden, prompt)

    assert [case.pair_id for case in quick.cases] == [
        pair["pair_id"] for pair in pairs[:6]
    ]
    assert len(full.cases) == 7
    assert quick.accuracy == full.accuracy == 1.0
    assert quick.hard_negative_accuracy == 1.0


def test_malformed_pair_reports_its_line_number(tmp_path: Path) -> None:
    """Malformed JSON is actionable rather than silently excluded."""
    golden = tmp_path / "golden.jsonl"
    golden.write_text("{not json}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="line 1"):
        golden_eval.load_pairs(golden)


def test_history_is_append_only_and_has_one_header(tmp_path: Path) -> None:
    """Each run records a compact timestamped result without rewriting evidence."""
    golden = tmp_path / "golden.jsonl"
    prompt = tmp_path / "prompt.md"
    history = tmp_path / "history.csv"
    prompt.write_text("prompt", encoding="utf-8")
    _write_pairs(golden, [_pair("gp-001", "DUPLICATE")])
    summary = golden_eval.evaluate(golden, prompt)

    golden_eval.append_history(summary, history)
    golden_eval.append_history(summary, history)

    with history.open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 2
    assert list(rows[0]) == [
        "timestamp",
        "prompt_hash",
        "model_id",
        "n",
        "accuracy",
        "dup_precision",
        "hard_negative_accuracy",
    ]


def test_inline_seeded_candidates_never_call_project_lookup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Cached/seeded evaluation remains offline and avoids live project lookup."""
    golden = tmp_path / "golden.jsonl"
    prompt = tmp_path / "prompt.md"
    prompt.write_text("prompt", encoding="utf-8")
    _write_pairs(golden, [_pair("gp-001", "DUPLICATE")])
    monkeypatch.setattr(
        golden_eval,
        "_load_project",
        lambda _: pytest.fail("seeded evaluation attempted local project lookup"),
    )

    assert golden_eval.evaluate(golden, prompt).accuracy == 1.0
