"""Embedding-provider boundary for Atlas11's local and Bedrock index paths."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Protocol

from agent.config import LOCAL_EMBEDDING_MODEL_ID, PipelineConfig
from agent.errors import EmbeddingProviderError, map_credential_error


class EmbeddingProvider(Protocol):
    """Create normalized vectors for index documents and retrieval queries."""

    name: str
    model_id: str

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed a non-empty sequence of index documents."""

    def embed_query(self, text: str) -> list[float]:
        """Embed one retrieval query."""


class LocalEmbeddingProvider:
    """Use a previously cached MiniLM model without permitting model downloads."""

    name = "local"
    model_id = LOCAL_EMBEDDING_MODEL_ID

    def __init__(self, model: object | None = None) -> None:
        if model is not None:
            self._model = model
            return
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                self.model_id,
                local_files_only=True,
            )
        except Exception as error:
            raise EmbeddingProviderError(
                "Local embedding model is unavailable in the local cache. "
                "Pre-download sentence-transformers/all-MiniLM-L6-v2 before running "
                "with EMBEDDINGS_PROVIDER=local."
            ) from error

    def _encode(self, texts: Sequence[str]) -> list[list[float]]:
        try:
            encoded = self._model.encode(list(texts), normalize_embeddings=True)
            vectors = encoded.tolist() if hasattr(encoded, "tolist") else encoded
            if not isinstance(vectors, list) or any(
                not isinstance(vector, list) or not vector for vector in vectors
            ):
                raise ValueError("embedding output was not a non-empty vector list")
            return [[float(value) for value in vector] for vector in vectors]
        except EmbeddingProviderError:
            raise
        except Exception as error:
            raise EmbeddingProviderError("Local embedding failed.") from error

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed documents with cached MiniLM and normalized output vectors."""
        return self._encode(texts)

    def embed_query(self, text: str) -> list[float]:
        """Embed one query with cached MiniLM and a normalized output vector."""
        return self._encode([text])[0]


class BedrockEmbeddingProvider:
    """Call Titan Text Embeddings V2 through a fresh bounded Bedrock client."""

    name = "bedrock"

    def __init__(self, config: PipelineConfig, client: object | None = None) -> None:
        self.model_id = config.bedrock_embedding_model_id
        if client is not None:
            self._client = client
            return
        try:
            import boto3
            from botocore.config import Config

            session = boto3.Session(region_name=config.aws_region)
            self._client = session.client(
                "bedrock-runtime",
                config=Config(
                    connect_timeout=20, read_timeout=20, retries={"max_attempts": 0}
                ),
            )
        except Exception as error:
            raise EmbeddingProviderError(
                "Unable to initialize Bedrock embeddings."
            ) from error

    def _embed(self, text: str) -> list[float]:
        try:
            response = self._client.invoke_model(
                modelId=self.model_id,
                body=json.dumps({"inputText": text}),
                contentType="application/json",
                accept="application/json",
            )
            body = response["body"].read()
            payload = json.loads(body)
            vector = payload.get("embedding")
            if not isinstance(vector, list) or not vector:
                raise ValueError("Titan response did not contain an embedding")
            return [float(value) for value in vector]
        except Exception as error:
            mapped = map_credential_error(error)
            if mapped is not error:
                raise mapped from error
            if isinstance(error, EmbeddingProviderError):
                raise
            raise EmbeddingProviderError("Bedrock embedding failed.") from error

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed documents through Titan, once per provided canonical document."""
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        """Embed one query through Titan."""
        return self._embed(text)


def create_embedding_provider(config: PipelineConfig) -> EmbeddingProvider:
    """Create only the explicitly configured provider; local mode never initializes AWS."""
    if config.embeddings_provider.value == "local":
        return LocalEmbeddingProvider()
    return BedrockEmbeddingProvider(config)
