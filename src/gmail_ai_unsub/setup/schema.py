"""Configuration schema definitions for the setup wizard.

This module defines the structure of configuration options in a data-driven way,
allowing the wizard to be generated from schema definitions rather than hardcoded prompts.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FieldType(Enum):
    """Types of configuration fields."""

    TEXT = "text"
    PASSWORD = "password"
    SELECT = "select"
    CONFIRM = "confirm"
    PATH = "path"
    FLOAT = "float"
    INT = "int"


@dataclass
class Choice:
    """A choice option for select fields."""

    value: str | None
    label: str
    description: str | None = None
    # Nested fields to show when this choice is selected
    nested_fields: list["ConfigField"] = field(default_factory=list)


@dataclass
class ConfigField:
    """Definition of a configuration field."""

    key: str  # TOML key path (e.g., "llm.provider")
    label: str  # Human-readable label
    field_type: FieldType
    description: str | None = None
    default: Any = None
    # For select fields
    choices: list[Choice] | None = None
    # Validation
    required: bool = True
    validator: Callable[[Any], bool | str] | None = None
    # Conditional display
    show_if: Callable[[dict[str, Any]], bool] | None = None
    # For numeric fields
    min_value: float | None = None
    max_value: float | None = None
    # Environment variable to check for default
    env_var: str | None = None
    # Help text shown below the field
    help_text: str | None = None


@dataclass
class ConfigSection:
    """A section of configuration fields."""

    key: str  # TOML section name
    title: str
    description: str | None = None
    icon: str = "⚙️"
    fields: list[ConfigField] = field(default_factory=list)
    # Whether this section is optional/advanced
    advanced: bool = False


# =============================================================================
# LLM Provider Definitions
# =============================================================================

# Models ordered by speed (fastest first for email classification)
GOOGLE_MODELS = [
    Choice(
        value="gemini-2.5-flash-lite",
        label="Gemini 2.5 Flash Lite",
        description="Fastest, good for simple classification",
    ),
    Choice(
        value="gemini-2.5-flash",
        label="Gemini 2.5 Flash",
        description="Fast and capable (recommended)",
    ),
    Choice(
        value="gemini-3-pro-preview",
        label="Gemini 3 Pro",
        description="Best quality with low reasoning mode",
    ),
]

ANTHROPIC_MODELS = [
    Choice(
        value="claude-4-5-haiku",
        label="Claude 4.5 Haiku",
        description="Fast and efficient (recommended)",
    ),
    Choice(
        value="claude-4-5-sonnet",
        label="Claude 4.5 Sonnet",
        description="More capable, slower",
    ),
]

OPENAI_MODELS = [
    Choice(
        value="gpt-5-nano",
        label="GPT-5 Nano",
        description="Fastest (recommended)",
    ),
    Choice(
        value="gpt-5-mini",
        label="GPT-5 Mini",
        description="Fast and capable",
    ),
    Choice(
        value="o4-mini",
        label="o4-mini",
        description="Reasoning model",
    ),
]

# Thinking level options for Gemini 2.5+ models
# Maps to thinking_budget ranges: "low" → 1-1000, "high" → 1000-32768
THINKING_LEVEL_OPTIONS = [
    Choice(
        value="low",
        label="Low",
        description="Faster, less reasoning (maps to budget 1-1000) - recommended",
    ),
    Choice(
        value="high",
        label="High",
        description="Deeper reasoning, slower (maps to budget 1000-32768)",
    ),
    Choice(value=None, label="Disabled", description="Fastest, no reasoning"),
]


def get_models_for_provider(provider: str) -> list[Choice]:
    """Get model choices for a provider."""
    return {
        "google": GOOGLE_MODELS,
        "anthropic": ANTHROPIC_MODELS,
        "openai": OPENAI_MODELS,
    }.get(provider, GOOGLE_MODELS)


def get_api_key_env_for_provider(provider: str) -> str:
    """Get the default API key environment variable for a provider."""
    return {
        "google": "GOOGLE_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
    }.get(provider, "GOOGLE_API_KEY")


# API key URLs for each provider
API_KEY_URLS = {
    "google": "https://aistudio.google.com/apikey",
    "anthropic": "https://console.anthropic.com/settings/keys",
    "openai": "https://platform.openai.com/api-keys",
}

# Provider display names
PROVIDER_NAMES = {
    "google": "Google AI Studio",
    "anthropic": "Anthropic Console",
    "openai": "OpenAI Platform",
}


def get_api_key_url(provider: str) -> str:
    """Get the URL to obtain an API key for a provider."""
    return API_KEY_URLS.get(provider, API_KEY_URLS["google"])


def get_provider_name(provider: str) -> str:
    """Get the display name for a provider."""
    return PROVIDER_NAMES.get(provider, "Google AI Studio")


# =============================================================================
# Configuration Schema Definition
# =============================================================================


def build_config_schema(
    config_dir: str,
    data_dir: str,
    state_dir: str,
    token_file: str,
    state_file: str,
) -> list[ConfigSection]:
    """Build the configuration schema with platform-specific paths.

    Args:
        config_dir: Platform-specific config directory
        data_dir: Platform-specific data directory
        state_dir: Platform-specific state directory
        token_file: Default token file path
        state_file: Default state file path

    Returns:
        List of configuration sections
    """
    return [
        ConfigSection(
            key="llm",
            title="LLM Provider",
            description="Configure which AI model to use for email classification",
            icon="🤖",
            fields=[
                ConfigField(
                    key="llm.provider",
                    label="AI Provider",
                    field_type=FieldType.SELECT,
                    description="Choose your preferred LLM provider",
                    default="google",
                    choices=[
                        Choice(
                            value="google",
                            label="Google Gemini",
                            description="Recommended - Best balance of quality and speed",
                        ),
                        Choice(
                            value="anthropic",
                            label="Anthropic Claude",
                            description="Excellent reasoning capabilities",
                        ),
                        Choice(
                            value="openai",
                            label="OpenAI",
                            description="GPT-5 and o-series reasoning models",
                        ),
                    ],
                ),
                ConfigField(
                    key="llm.model",
                    label="Model",
                    field_type=FieldType.SELECT,
                    description="Select the specific model to use",
                    default="gemini-2.5-flash",  # Fast model by default
                    # Choices are dynamically set based on provider
                    choices=GOOGLE_MODELS,
                ),
            ],
        ),
        ConfigSection(
            key="llm_advanced",
            title="Advanced LLM Settings",
            description="Fine-tune model behavior (most users don't need to change these)",
            icon="⚙️",
            advanced=True,
            fields=[
                ConfigField(
                    key="llm.temperature",
                    label="Temperature",
                    field_type=FieldType.FLOAT,
                    description="Controls output randomness (0.0-1.0)",
                    default=None,  # Let model use its default
                    min_value=0.0,
                    max_value=1.0,
                    help_text="Leave empty to use model default. Some models perform poorly with custom temperatures.",
                    required=False,
                ),
                ConfigField(
                    key="llm.thinking_level",
                    label="Thinking Level",
                    field_type=FieldType.SELECT,
                    description="Reasoning level (Gemini 2.5+ only)",
                    default="low",  # Low reasoning by default for balanced speed/quality
                    choices=THINKING_LEVEL_OPTIONS,
                    help_text="Maps to thinking_budget: low (1-1000), high (1000-32768)",
                    required=False,
                ),
                ConfigField(
                    key="llm.max_tokens",
                    label="Max Tokens",
                    field_type=FieldType.INT,
                    description="Maximum output tokens",
                    default=None,
                    min_value=100,
                    max_value=100000,
                    help_text="Leave empty to use model default",
                    required=False,
                ),
            ],
        ),
        ConfigSection(
            key="gmail",
            title="Gmail API",
            description="Configure Gmail API authentication",
            icon="📧",
            advanced=True,  # Most users won't need to change these
            fields=[
                ConfigField(
                    key="gmail.credentials_file",
                    label="Custom Credentials File (Optional)",
                    field_type=FieldType.PATH,
                    description="Path to custom OAuth2 credentials.json (leave empty to use default)",
                    default="",
                    help_text="Only needed if you want to use your own OAuth app instead of the built-in one",
                    required=False,
                ),
                ConfigField(
                    key="gmail.token_file",
                    label="Token File",
                    field_type=FieldType.PATH,
                    description="Where to cache your Gmail OAuth token after login",
                    default=token_file,
                    help_text="This file stores your authenticated session so you don't have to log in every time",
                ),
            ],
        ),
        ConfigSection(
            key="labels",
            title="Gmail Labels",
            description="Labels for organizing emails and triggering actions",
            icon="🏷️",
            fields=[
                ConfigField(
                    key="labels.marketing",
                    label="Unsubscribe Label",
                    field_type=FieldType.TEXT,
                    description="Label for emails you want to unsubscribe from",
                    default="Unsubscribe",
                    help_text="Apply this label to any email to trigger unsubscription (AI or manual)",
                ),
                ConfigField(
                    key="labels.unsubscribed",
                    label="Completed Label",
                    field_type=FieldType.TEXT,
                    description="Label applied after successful unsubscription",
                    default="Unsubscribed",
                ),
                ConfigField(
                    key="labels.failed",
                    label="Failed Label",
                    field_type=FieldType.TEXT,
                    description="Label applied when unsubscription fails",
                    default="Unsubscribe-Failed",
                    help_text="Review these emails to manually unsubscribe",
                ),
            ],
        ),
        ConfigSection(
            key="storage",
            title="Storage",
            description="Where to store application state",
            icon="💾",
            advanced=True,
            fields=[
                ConfigField(
                    key="storage.state_file",
                    label="State File",
                    field_type=FieldType.PATH,
                    description="Path to the state file",
                    default=state_file,
                ),
            ],
        ),
        ConfigSection(
            key="unsubscribe",
            title="Browser Automation",
            description="Settings for automated unsubscription",
            icon="🌐",
            fields=[
                ConfigField(
                    key="unsubscribe.headless",
                    label="Headless Mode",
                    field_type=FieldType.CONFIRM,
                    description="Run browser without visible window",
                    default=True,
                    help_text="Set to No to see the browser during automation (useful for debugging)",
                ),
                ConfigField(
                    key="unsubscribe.browser_timeout",
                    label="Browser Timeout",
                    field_type=FieldType.INT,
                    description="Timeout for browser operations (seconds)",
                    default=60,
                    min_value=10,
                    max_value=300,
                ),
                ConfigField(
                    key="unsubscribe.enable_mailto",
                    label="Enable Mailto Unsubscribe",
                    field_type=FieldType.CONFIRM,
                    description="Allow sending emails for mailto: unsubscribe links",
                    default=True,
                ),
            ],
        ),
        ConfigSection(
            key="prompts",
            title="Email Preferences",
            description="Tell us what emails you want to keep or avoid (optional)",
            icon="💬",
            advanced=False,
            fields=[
                ConfigField(
                    key="prompts.user_preferences",
                    label="Email Preferences",
                    field_type=FieldType.TEXT,
                    description="Describe what emails you want to keep or avoid in free form",
                    default="",
                    required=False,
                    help_text="Example: 'Keep podcast episode notifications, NPR newsletters, and Stratechery. Unsubscribe from all other Substack and Medium newsletters. Keep emails from Red Cross and local news.' This will be added to the classification prompt to help the AI understand your preferences.",
                ),
            ],
        ),
    ]
