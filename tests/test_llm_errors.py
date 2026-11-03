"""Tests for LLM provider failure detection."""

import pytest

from gmail_ai_unsub.unsubscribe.llm_errors import is_fatal_llm_error


@pytest.mark.parametrize(
    "message",
    [
        "402 RESOURCE_EXHAUSTED. Your prepayment credits are depleted. Please go to AI Studio",
        "Your credit balance is too low to access the Anthropic API",
        "Error code: 429 - insufficient_quota: You exceeded your current quota",
        "400 API key not valid. Please pass a valid API key.",
        "403 PERMISSION_DENIED: The caller does not have permission",
        "401 UNAUTHENTICATED: Request had invalid authentication credentials",
    ],
)
def test_fatal_llm_errors_detected(message: str) -> None:
    assert is_fatal_llm_error(message)


@pytest.mark.parametrize(
    "message",
    [
        "429 RESOURCE_EXHAUSTED: Quota exceeded for requests per minute",
        "Browser error: net::ERR_NAME_NOT_RESOLVED",
        "Navigation failed: HTTP 403 Forbidden",
        "Browser automation did not complete successfully",
    ],
)
def test_transient_or_page_errors_not_fatal(message: str) -> None:
    assert not is_fatal_llm_error(message)
