"""Detection of LLM provider failures that make every further request fail."""

# Provider messages meaning the LLM can't serve any request (billing, auth,
# quota), so retrying other emails would fail the same way. Deliberately specific:
# a plain 429 rate limit or an HTTP 403 from an unsubscribe page is not fatal.
_FATAL_LLM_ERROR_MARKERS = (
    "prepayment credits",  # Gemini 402
    "credits are depleted",
    "credit balance is too low",  # Anthropic
    "insufficient_quota",  # OpenAI
    "api key not valid",  # Gemini
    "invalid_api_key",
    "invalid x-api-key",
    "permission_denied",
    "unauthenticated",
    "authentication_error",
)


class LLMUnavailableError(Exception):
    """The browser LLM can't be used (billing, auth or quota); retrying won't help."""


def is_fatal_llm_error(message: str) -> bool:
    """Whether an error message means the LLM provider is unusable for every request."""
    lowered = message.lower()
    return any(marker in lowered for marker in _FATAL_LLM_ERROR_MARKERS)
