"""Run deterministic golden-pair evaluation without live cloud dependencies."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from agent.schemas import Project, ProposalCreate, VerdictLabel
from agent.tools.get_project import _load_project

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLDEN_PATH = ROOT / "data" / "eval" / "golden_pairs.jsonl"
DEFAULT_HISTORY_PATH = ROOT / ".kiro" / "evidence" / "eval-history.csv"
DEFAULT_PROMPT_PATH = ROOT / "agent" / "prompts" / "clash_system.md"
MODEL_ID = "deterministic-eval-v1"
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


class GoldenPair(BaseModel):
    """One human-labelled proposal and funded-project comparison case."""

    model_config = ConfigDict(extra="ignore")

    pair_id: str = Field(min_length=1)
    proposal: ProposalCreate
    project_id: str = Field(min_length=1)
    expected: VerdictLabel
    rationale: str = Field(min_length=1)
    labelled_by: str = Field(min_length=1)
    source: Literal["worldbank_api", "iati", "seeded"]
    candidate: Project | None = None
    hard_negative: bool = False

    @model_validator(mode="after")
    def seeded_candidate_matches_id(self) -> "GoldenPair":
        """Keep optional seeded candidates tied to their cited canonical IDs."""
        if self.candidate is not None and self.candidate.project_id != self.project_id:
            raise ValueError("candidate.project_id must match project_id")
        return self


@dataclass(frozen=True, slots=True)
class CaseResult:
    """One evaluated case with its expected and deterministic labels."""

    pair_id: str
    expected: VerdictLabel
    actual: VerdictLabel
    hard_negative: bool
    rationale: str

    @property
    def correct(self) -> bool:
        """Return whether the deterministic label matches the human reference."""
        return self.expected is self.actual


@dataclass(frozen=True, slots=True)
class EvaluationSummary:
    """Serializable aggregate output for one quick or full evaluation run."""

    mode: str
    prompt_hash: str
    cases: tuple[CaseResult, ...]

    @property
    def accuracy(self) -> float:
        """Return exact-label accuracy, or zero for an empty invalid run."""
        return (
            sum(case.correct for case in self.cases) / len(self.cases)
            if self.cases
            else 0.0
        )

    @property
    def duplicate_precision(self) -> float:
        """Return precision for the highest-severity duplicate classification."""
        predicted = [
            case for case in self.cases if case.actual is VerdictLabel.DUPLICATE
        ]
        return (
            sum(case.correct for case in predicted) / len(predicted)
            if predicted
            else 1.0
        )

    @property
    def hard_negative_accuracy(self) -> float:
        """Return accuracy over explicitly marked look-alike negative cases."""
        hard_negatives = [case for case in self.cases if case.hard_negative]
        return (
            sum(case.correct for case in hard_negatives) / len(hard_negatives)
            if hard_negatives
            else 1.0
        )

    def to_dict(self) -> dict[str, object]:
        """Return a concise non-secret report suitable for CLI and test assertions."""
        confusion = Counter(
            f"{case.expected.value}->{case.actual.value}" for case in self.cases
        )
        failures = [
            {
                "pair_id": case.pair_id,
                "expected": case.expected.value,
                "actual": case.actual.value,
                "rationale": case.rationale,
            }
            for case in self.cases
            if not case.correct
        ]
        return {
            "mode": self.mode,
            "model_id": MODEL_ID,
            "n": len(self.cases),
            "accuracy": round(self.accuracy, 4),
            "duplicate_precision": round(self.duplicate_precision, 4),
            "hard_negative_accuracy": round(self.hard_negative_accuracy, 4),
            "confusion": dict(sorted(confusion.items())),
            "failures": failures,
        }


def load_pairs(golden_path: Path) -> list[GoldenPair]:
    """Load every labelled line, naming malformed records with their line number."""
    pairs: list[GoldenPair] = []
    seen_ids: set[str] = set()
    for line_number, line in enumerate(
        golden_path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            pair = GoldenPair.model_validate_json(line)
        except ValidationError as error:
            raise ValueError(
                f"Malformed golden pair at line {line_number}: {error}"
            ) from error
        if pair.pair_id in seen_ids:
            raise ValueError(
                f"Malformed golden pair at line {line_number}: duplicate pair_id={pair.pair_id}"
            )
        seen_ids.add(pair.pair_id)
        pairs.append(pair)
    if not pairs:
        raise ValueError("No valid golden pairs found")
    return pairs


def _project_for(pair: GoldenPair) -> Project:
    """Use an explicitly seeded candidate or the canonical local project source."""
    return (
        pair.candidate if pair.candidate is not None else _load_project(pair.project_id)
    )


def _tokens(value: str) -> set[str]:
    """Normalize short project titles for conservative duplicate evidence."""
    return set(_TOKEN_PATTERN.findall(value.casefold()))


def _title_similarity(proposal: ProposalCreate, project: Project) -> float:
    """Return title-token recall against a cited project name without embeddings."""
    project_tokens = _tokens(project.name)
    proposal_tokens = _tokens(f"{proposal.title} {proposal.description}")
    return (
        len(project_tokens & proposal_tokens) / len(project_tokens)
        if project_tokens
        else 0.0
    )


def _dates_overlap(proposal: ProposalCreate, project: Project) -> bool:
    """Apply the same inclusive 12-month-slack date rule used by overlap tooling."""
    if None in (
        proposal.start_date,
        proposal.end_date,
        project.approval_date,
        project.closing_date,
    ):
        return False
    assert proposal.start_date is not None and proposal.end_date is not None
    assert project.approval_date is not None and project.closing_date is not None
    return proposal.start_date <= _add_months(
        project.closing_date, 12
    ) and project.approval_date <= _add_months(proposal.end_date, 12)


def _add_months(value: datetime.date, months: int) -> datetime.date:
    """Shift a date by whole months while retaining a valid calendar day."""
    import calendar

    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return value.replace(
        year=year, month=month, day=min(value.day, calendar.monthrange(year, month)[1])
    )


def _has_distinct_scope(proposal: ProposalCreate) -> bool:
    """Recognize proposal text that explicitly declares an additional scope component."""
    text = f"{proposal.title} {proposal.description}".casefold()
    return any(
        marker in text for marker in ("distinct", "alongside", "adds a separate")
    )


def classify(pair: GoldenPair) -> VerdictLabel:
    """Classify one pair from local cited data using conservative taxonomy rules."""
    project = _project_for(pair)
    proposal = pair.proposal
    if proposal.city_id != project.city:
        return VerdictLabel.UNRELATED
    if (
        proposal.district_id
        and project.district
        and proposal.district_id != project.district
    ):
        return VerdictLabel.UNRELATED
    if not _dates_overlap(proposal, project):
        return VerdictLabel.COMPLEMENTARY
    if proposal.sector.casefold() != project.sector.casefold():
        return VerdictLabel.COMPLEMENTARY
    if _has_distinct_scope(proposal):
        return VerdictLabel.OVERLAPPING
    if _title_similarity(proposal, project) >= 0.60:
        return VerdictLabel.DUPLICATE
    return VerdictLabel.OVERLAPPING


def prompt_hash(prompt_path: Path) -> str:
    """Return the stable short hash recorded with an evaluation run."""
    return hashlib.sha256(prompt_path.read_bytes()).hexdigest()[:12]


def evaluate(
    golden_path: Path, prompt_path: Path, quick: bool = False
) -> EvaluationSummary:
    """Evaluate quick first-six or full labelled pairs without AWS, Chroma, or Bedrock."""
    pairs = load_pairs(golden_path)
    selected = pairs[:6] if quick else pairs
    cases = tuple(
        CaseResult(
            pair_id=pair.pair_id,
            expected=pair.expected,
            actual=classify(pair),
            hard_negative=pair.hard_negative,
            rationale=pair.rationale,
        )
        for pair in selected
    )
    return EvaluationSummary(
        mode="quick" if quick else "full",
        prompt_hash=prompt_hash(prompt_path),
        cases=cases,
    )


def append_history(summary: EvaluationSummary, history_path: Path) -> None:
    """Append one timestamped, secret-free row without rewriting prior evidence."""
    history_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not history_path.exists()
    with history_path.open("a", newline="", encoding="utf-8") as history:
        writer = csv.DictWriter(
            history,
            fieldnames=(
                "timestamp",
                "prompt_hash",
                "model_id",
                "n",
                "accuracy",
                "dup_precision",
                "hard_negative_accuracy",
            ),
        )
        if new_file:
            writer.writeheader()
        writer.writerow(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "prompt_hash": summary.prompt_hash,
                "model_id": MODEL_ID,
                "n": len(summary.cases),
                "accuracy": f"{summary.accuracy:.4f}",
                "dup_precision": f"{summary.duplicate_precision:.4f}",
                "hard_negative_accuracy": f"{summary.hard_negative_accuracy:.4f}",
            }
        )


def _regressed(summary: EvaluationSummary, history_path: Path) -> bool:
    """Detect a lower quick accuracy than the latest prior quick run, if any."""
    if not history_path.exists():
        return False
    with history_path.open(newline="", encoding="utf-8") as history:
        prior = list(csv.DictReader(history))
    quick_runs = [row for row in prior if row.get("n") == str(len(summary.cases))]
    return bool(quick_runs) and summary.accuracy < float(quick_runs[-1]["accuracy"])


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return a nonzero status for malformed data or regressions."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--quick", action="store_true", help="Evaluate the first six valid pairs."
    )
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Exit nonzero when accuracy is lower than the prior equivalent run.",
    )
    parser.add_argument("--golden-path", type=Path, default=DEFAULT_GOLDEN_PATH)
    parser.add_argument("--history-path", type=Path, default=DEFAULT_HISTORY_PATH)
    parser.add_argument("--prompt-path", type=Path, default=DEFAULT_PROMPT_PATH)
    args = parser.parse_args(argv)
    try:
        summary = evaluate(args.golden_path, args.prompt_path, quick=args.quick)
        regressed = args.fail_on_regression and _regressed(summary, args.history_path)
        append_history(summary, args.history_path)
    except (OSError, ValueError, ValidationError) as error:
        print(f"Evaluation failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(summary.to_dict(), indent=2, sort_keys=True))
    if regressed:
        print(
            "Evaluation regressed from the prior equivalent run; human review is required.",
            file=sys.stderr,
        )
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
