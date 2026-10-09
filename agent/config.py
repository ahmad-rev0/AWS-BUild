"""Typed environment configuration for the Atlas11 data pipeline."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from dotenv import load_dotenv

from agent.errors import UnsupportedEmbeddingProviderError


class EmbeddingsProvider(StrEnum):
    """Embedding providers supported by the pipeline."""

    BEDROCK = "bedrock"
    LOCAL = "local"


DEFAULT_BEDROCK_EMBEDDING_MODEL_ID: Final[str] = "amazon.titan-embed-text-v2:0"
DEFAULT_BEDROCK_NOVA_MODEL_ID: Final[str] = "us.amazon.nova-pro-v1:0"
DEFAULT_AWS_REGION: Final[str] = "us-east-1"
DEFAULT_CHROMA_COLLECTION: Final[str] = "projects"
LOCAL_EMBEDDING_MODEL_ID: Final[str] = "sentence-transformers/all-MiniLM-L6-v2"


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    """Resolved configuration required by index, retrieval, and AWS diagnostics."""

    embeddings_provider: EmbeddingsProvider
    bedrock_embedding_model_id: str
    bedrock_nova_model_id: str
    aws_region: str
    chroma_path: Path
    chroma_collection: str
    demo_mode: str | None

    @classmethod
    def from_environment(cls, root: Path) -> "PipelineConfig":
        """Load current environment values and optional agent/.env values for one invocation."""

        load_dotenv(root / "agent" / ".env", override=True)
        provider_value = os.getenv("EMBEDDINGS_PROVIDER", EmbeddingsProvider.LOCAL.value)
        try:
            provider = EmbeddingsProvider(provider_value.strip().lower())
        except ValueError as error:
            allowed = ", ".join(member.value for member in EmbeddingsProvider)
            raise UnsupportedEmbeddingProviderError(
                f"Unsupported EMBEDDINGS_PROVIDER={provider_value!r}; use one of: {allowed}."
            ) from error

        chroma_value = os.getenv("CHROMA_PATH", "data/index")
        chroma_path = Path(chroma_value)
        if not chroma_path.is_absolute():
            chroma_path = root / chroma_path

        return cls(
            embeddings_provider=provider,
            bedrock_embedding_model_id=os.getenv(
                "BEDROCK_EMBEDDING_MODEL_ID", DEFAULT_BEDROCK_EMBEDDING_MODEL_ID
            ),
            bedrock_nova_model_id=os.getenv("BEDROCK_NOVA_MODEL_ID", DEFAULT_BEDROCK_NOVA_MODEL_ID),
            aws_region=os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", DEFAULT_AWS_REGION)),
            chroma_path=chroma_path,
            chroma_collection=os.getenv("CHROMA_COLLECTION", DEFAULT_CHROMA_COLLECTION),
            demo_mode=os.getenv("DEMO_MODE"),
        )
