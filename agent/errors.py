"""Typed exceptions for Atlas11 pipeline and retrieval boundaries."""

from __future__ import annotations

from typing import Final

CREDENTIALS_EXPIRED_MESSAGE: Final[str] = (
    "AWS credentials expired. Refresh agent/.env from Workshop Studio."
)


class PipelineError(Exception):
    """Base exception for expected data-pipeline failures."""


class ConfigurationError(PipelineError):
    """Raised when pipeline configuration is missing or invalid."""


class UnsupportedEmbeddingProviderError(ConfigurationError):
    """Raised when EMBEDDINGS_PROVIDER is not a supported provider name."""


class MissingDataError(PipelineError):
    """Raised when required project data is absent or cannot be read."""


class SearchInputError(PipelineError):
    """Raised before querying Chroma when search text, limits, or filters are invalid."""


class ProjectNotFoundError(PipelineError):
    """Raised when a canonical project is absent from the local project source."""

    def __init__(self, project_id: str) -> None:
        super().__init__(f"Project not found: {project_id}")


class EmbeddingProviderError(PipelineError):
    """Raised when the configured embedding provider cannot create embeddings."""


class CredentialsExpired(EmbeddingProviderError):
    """Raised when AWS credentials are expired or rejected by Bedrock."""

    def __init__(self) -> None:
        super().__init__(CREDENTIALS_EXPIRED_MESSAGE)


def is_expired_credentials_error(error: BaseException) -> bool:
    """Return whether an AWS exception represents expired or invalid credentials."""

    error_code = ""
    response = getattr(error, "response", None)
    if isinstance(response, dict):
        nested_error = response.get("Error", {})
        if isinstance(nested_error, dict):
            code = nested_error.get("Code", "")
            error_code = code if isinstance(code, str) else ""

    return error_code in {
        "ExpiredToken",
        "ExpiredTokenException",
        "UnrecognizedClientException",
    }


def map_credential_error(error: BaseException) -> BaseException:
    """Map known AWS credential failures to CredentialsExpired unchanged otherwise."""

    if is_expired_credentials_error(error):
        return CredentialsExpired()
    return error
