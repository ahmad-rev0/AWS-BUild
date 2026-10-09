"""Return a bounded list of similar funded projects for a proposal.

Use this tool first to identify candidate projects. Provide the proposal text and request
between one and eight results. The response contains only canonical project IDs and
normalized similarity scores; call ``get_project`` for a project's full evidence.
"""

from pydantic import BaseModel, ConfigDict, Field

from agent.schemas import Candidate


class SimilarProjectSearchInput(BaseModel):
    """Validated arguments for the bounded shared project retrieval search."""

    model_config = ConfigDict(str_strip_whitespace=True)

    proposal_text: str = Field(min_length=1)
    k: int = Field(default=8, ge=1, le=8)


class SimilarProjectSearchOutput(BaseModel):
    """Model-facing candidate identifiers and normalized similarity scores only."""

    candidates: list[Candidate] = Field(default_factory=list)


def search_similar_projects(
    proposal_text: str,
    k: int = 8,
) -> SimilarProjectSearchOutput:
    """Find up to eight similar funded projects by proposal text.

    Use this before requesting project details. Pass non-empty proposal text and a value
    from 1 through 8 for ``k``. The result contains only stable project IDs and normalized
    similarity scores, not project descriptions or inferred clash decisions.
    """
    request = SimilarProjectSearchInput(proposal_text=proposal_text, k=k)

    from agent.retrieval import search

    retrieved_candidates = search(request.proposal_text, k=request.k)
    candidates: list[Candidate] = []
    seen_project_ids: set[str] = set()
    for retrieved_candidate in retrieved_candidates:
        candidate = Candidate.model_validate(retrieved_candidate)
        if candidate.project_id in seen_project_ids:
            continue
        seen_project_ids.add(candidate.project_id)
        candidates.append(candidate)
        if len(candidates) == request.k:
            break

    return SimilarProjectSearchOutput(candidates=candidates)
