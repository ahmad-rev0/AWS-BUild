"""Create a deterministic, non-financial coordination memo from validated verdicts."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agent.schemas import Memo, Recommendation, Verdict, VerdictLabel


class DraftMemoInput(BaseModel):
    """Validated verdicts from which to select one coordination recommendation."""

    verdicts: list[Verdict] = Field(min_length=1)


def draft_memo(verdicts: list[Verdict]) -> Memo:
    """Draft one coordination memo from validated verdicts without making funding decisions.

    Duplicate evidence recommends MERGE, overlapping evidence recommends CO_FINANCE,
    and all other evidence recommends PROCEED. This tool does not create REDIRECT
    recommendations because verdicts contain no validated district target. Any
    REDIRECT Memo must name only a coordination and map-focus target; it must not
    allocate, increase, transfer, or claim funding commitments.
    """
    validated = DraftMemoInput(verdicts=verdicts)
    labels = {verdict.label for verdict in validated.verdicts}

    if VerdictLabel.DUPLICATE in labels:
        return Memo(
            recommendation=Recommendation.MERGE,
            summary=(
                "Coordinate a merged scope with the cited project owners before proceeding. "
                "This is a coordination recommendation only and does not move or allocate funds."
            ),
        )
    if VerdictLabel.OVERLAPPING in labels:
        return Memo(
            recommendation=Recommendation.CO_FINANCE,
            summary=(
                "Coordinate shared scope with the cited project owners, including possible co-finance "
                "discussions. This recommendation does not allocate, transfer, or increase funding."
            ),
        )
    return Memo(
        recommendation=Recommendation.PROCEED,
        summary=(
            "Proceed with normal coordination and retain the cited projects for context. "
            "This recommendation does not allocate, transfer, or increase funding."
        ),
    )
