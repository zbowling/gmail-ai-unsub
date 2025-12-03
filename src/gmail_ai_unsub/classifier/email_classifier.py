"""Email classification using LangChain and LLMs."""

from typing import Any, Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field


class ClassificationResult(BaseModel):
    """Result of email classification."""

    is_marketing: bool = Field(..., description="Whether the email is marketing/promotional")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0 and 1")
    reason: str = Field(..., description="Brief explanation of the classification")


class EmailClassifier:
    """Classify emails as marketing using LLMs."""

    def __init__(
        self,
        llm: BaseChatModel,
        system_prompt: str,
        marketing_criteria: str,
        exclusions: str,
        user_preferences: str = "",
    ) -> None:
        """Initialize email classifier.

        Args:
            llm: LangChain chat model instance
            system_prompt: System prompt for the classifier
            marketing_criteria: Description of what constitutes marketing emails
            exclusions: What to exclude from marketing classification
            user_preferences: Free-form user preferences for what emails to keep or avoid
        """
        self.llm = llm
        self.system_prompt = system_prompt
        self.marketing_criteria = marketing_criteria
        self.exclusions = exclusions
        self.user_preferences = user_preferences
        self.prompt = self._build_prompt(system_prompt, marketing_criteria, exclusions)

    def _build_exclusions_text(self) -> str:
        """Build the complete exclusions text with user preferences."""
        exclusions_text = self.exclusions

        # Add user preferences if provided
        if self.user_preferences.strip():
            exclusions_text += "\n\nUser Preferences:\n" + self.user_preferences

        return exclusions_text

    def _build_prompt(
        self,
        system_prompt: str,
        marketing_criteria: str,
        exclusions: str,
    ) -> ChatPromptTemplate:
        """Build the classification prompt template."""
        return ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                (
                    "human",
                    """Analyze the following email and determine if it is a marketing or promotional email.

Marketing Criteria:
{marketing_criteria}

Exclusions:
{exclusions}

Email Subject: {subject}
Email From: {from_address}
Email Body (first 2000 chars): {body}

Respond with:
- is_marketing: true or false
- confidence: a number between 0.0 and 1.0
- reason: a brief explanation (1-2 sentences)

Email to classify:
""",
                ),
            ]
        )

    async def classify(self, subject: str, from_address: str, body: str) -> ClassificationResult:
        """Classify an email as marketing or not.

        Args:
            subject: Email subject line
            from_address: Email sender address
            body: Email body text (first 2000 chars recommended)

        Returns:
            ClassificationResult with is_marketing, confidence, and reason
        """
        # Truncate body to avoid token limits
        body_truncated = body[:2000] if len(body) > 2000 else body

        # Build exclusions text with additional preferences
        exclusions_text = self._build_exclusions_text()

        # Format prompt with email data
        messages = self.prompt.format_messages(
            marketing_criteria=self.marketing_criteria,
            exclusions=exclusions_text,
            subject=subject,
            from_address=from_address,
            body=body_truncated,
        )

        # Get structured output using Pydantic
        structured_llm = self.llm.with_structured_output(ClassificationResult)
        result = await structured_llm.ainvoke(messages)

        # Type narrowing: with_structured_output returns ClassificationResult
        assert isinstance(result, ClassificationResult)
        return result

    def classify_sync(self, subject: str, from_address: str, body: str) -> ClassificationResult:
        """Synchronous version of classify (for non-async contexts).

        Args:
            subject: Email subject line
            from_address: Email sender address
            body: Email body text

        Returns:
            ClassificationResult
        """
        body_truncated = body[:2000] if len(body) > 2000 else body

        # Build exclusions text with additional preferences
        exclusions_text = self._build_exclusions_text()

        messages = self.prompt.format_messages(
            marketing_criteria=self.marketing_criteria,
            exclusions=exclusions_text,
            subject=subject,
            from_address=from_address,
            body=body_truncated,
        )

        structured_llm = self.llm.with_structured_output(ClassificationResult)
        result = structured_llm.invoke(messages)

        # Type narrowing: with_structured_output returns ClassificationResult
        assert isinstance(result, ClassificationResult)
        return result


def create_classifier(
    provider: Literal["google", "anthropic", "openai"],
    model: str,
    api_key: str,
    system_prompt: str,
    marketing_criteria: str,
    exclusions: str,
    temperature: float | None = None,
    thinking_level: str | None = None,
    max_tokens: int | None = None,
    user_preferences: str = "",
) -> EmailClassifier:
    """Factory function to create a classifier with the specified provider.

    Args:
        provider: LLM provider name
        model: Model name
        api_key: API key for the provider
        system_prompt: System prompt
        marketing_criteria: Marketing criteria description
        exclusions: Exclusions description
        temperature: Temperature for generation (0.0-1.0). None uses model default.
            Some models perform poorly with custom temperatures.
        thinking_level: Reasoning level for Gemini 2.5+ models.
            - "low": Maps to thinking_budget 512 (minimum, faster)
            - "high": Maps to thinking_budget 16384 (deeper reasoning, slower)
            - None: Disabled (fastest, no thinking tokens)
        max_tokens: Maximum tokens for output. None uses model default.

    Returns:
        EmailClassifier instance
    """
    if provider == "google":
        # Build kwargs for Gemini
        gemini_kwargs: dict[str, Any] = {
            "model": model,
            "google_api_key": api_key,
        }
        # Only set temperature if explicitly provided
        if temperature is not None:
            gemini_kwargs["temperature"] = temperature
        if max_tokens is not None:
            gemini_kwargs["max_output_tokens"] = max_tokens

        # Gemini 2.5+ models support thinking_budget parameter
        # Valid range is 512 to 24576 tokens
        # Map thinking_level to thinking_budget:
        # "low" → 512 (minimum, faster responses)
        # "high" → 16384 (deeper reasoning, slower)
        if thinking_level == "low":
            gemini_kwargs["thinking_budget"] = 512
        elif thinking_level == "high":
            gemini_kwargs["thinking_budget"] = 16384
        # None means disabled (fastest, no thinking tokens)

        llm: BaseChatModel = ChatGoogleGenerativeAI(**gemini_kwargs)

    elif provider == "anthropic":
        anthropic_kwargs: dict[str, Any] = {
            "model": model,
            "anthropic_api_key": api_key,
        }
        # Only set temperature if explicitly provided
        if temperature is not None:
            anthropic_kwargs["temperature"] = temperature
        if max_tokens is not None:
            anthropic_kwargs["max_tokens"] = max_tokens

        llm = ChatAnthropic(**anthropic_kwargs)

    elif provider == "openai":
        from langchain_openai import ChatOpenAI

        openai_kwargs: dict[str, Any] = {
            "model": model,
            "openai_api_key": api_key,
        }
        # Only set temperature if explicitly provided
        if temperature is not None:
            openai_kwargs["temperature"] = temperature
        if max_tokens is not None:
            openai_kwargs["max_tokens"] = max_tokens

        # Note: OpenAI o-series models have their own reasoning approach
        # but don't need special configuration for basic use

        llm = ChatOpenAI(**openai_kwargs)

    else:
        raise ValueError(f"Unknown provider: {provider}")

    return EmailClassifier(
        llm,
        system_prompt,
        marketing_criteria,
        exclusions,
        user_preferences=user_preferences,
    )
