"""Configuration management using TOML."""

import os
import tomllib  # Python 3.11+ (standard library)
from pathlib import Path
from typing import Any

from gmail_ai_unsub.paths import find_config_file, get_config_file, get_state_file, get_token_file
from gmail_ai_unsub.storage import expand_path


class Config:
    """Application configuration loaded from TOML."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        """Initialize configuration from TOML file.

        Args:
            config_path: Path to config.toml file. If None, searches for
                config.toml in:
                1. Current directory
                2. XDG config directory (e.g., ~/.config/gmail-ai-unsub on Linux)
                3. Legacy location (~/.gmail-ai-unsub)
        """
        if config_path is None:
            found_config = find_config_file()
            if found_config is None:
                xdg_config = get_config_file()
                raise FileNotFoundError(
                    f"Config file not found. Expected config.toml in:\n"
                    f"  - Current directory (./config.toml)\n"
                    f"  - {xdg_config}\n"
                    f"\nRun 'gmail-unsub setup' to create a config file."
                )
            config_path = found_config

        self.config_path = Path(config_path)
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(self.config_path, "rb") as f:
            self._data = tomllib.load(f)

    def _get(self, *keys: str, default: Any = None) -> Any:
        """Get nested config value using dot notation."""
        value: Any = self._data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default
        return value

    @property
    def gmail_credentials_file(self) -> str | None:
        """Path to Gmail OAuth credentials JSON file.

        Returns None if not set, which means use the built-in default credentials.
        Users can provide their own credentials.json if they want to use their own
        OAuth app instead of the embedded one.
        """
        value = self._get("gmail", "credentials_file", default="")
        if not value:
            return None
        return expand_path(value)

    @property
    def gmail_token_file(self) -> str:
        """Path to Gmail OAuth token cache file."""
        default = str(get_token_file())
        return expand_path(self._get("gmail", "token_file", default=default))

    @property
    def llm_provider(self) -> str:
        """LLM provider: 'google', 'anthropic', or 'openai'."""
        return self._get("llm", "provider", default="google")

    @property
    def llm_model(self) -> str:
        """LLM model name."""
        return self._get("llm", "model", default="gemini-2.5-flash")

    @property
    def llm_api_key_env(self) -> str:
        """Environment variable name containing API key."""
        return self._get("llm", "api_key_env", default="GOOGLE_API_KEY")

    @property
    def llm_temperature(self) -> float | None:
        """Temperature for LLM generation (0.0-1.0).

        Lower values produce more consistent/deterministic results.
        Higher values produce more creative/varied results.

        Returns None if not set, which lets the model use its default.
        Some models (like Gemini) perform poorly with custom temperatures.
        """
        value = self._get("llm", "temperature", default=None)
        if value is None:
            return None
        return float(value)

    @property
    def llm_thinking_level(self) -> str | None:
        """Reasoning level for Gemini 2.5+ models.

        Maps to thinking_budget ranges per Google's API:
        - "low": Maps to thinking_budget 1-1000 (faster, less reasoning) - default
        - "high": Maps to thinking_budget 1000-32768 (deeper reasoning, slower)
        - None: Disabled (fastest, no reasoning)

        Returns "low" by default for balanced speed and quality.
        """
        return self._get("llm", "thinking_level", default="low")

    @property
    def llm_max_tokens(self) -> int | None:
        """Maximum tokens for LLM output. None uses model default."""
        return self._get("llm", "max_tokens", default=None)

    @property
    def llm_api_key(self) -> str:
        """Get API key from config file or environment variable.

        Priority:
        1. api_key in config.toml [llm] section
        2. Environment variable (e.g., GOOGLE_API_KEY)
        """
        # First try config file
        config_key = self._get("llm", "api_key", default=None)
        if config_key:
            return config_key

        # Fall back to environment variable
        env_var = self.llm_api_key_env
        api_key = os.getenv(env_var)
        if api_key:
            return api_key

        raise ValueError(
            f"API key not found. Either:\n"
            f"  1. Add 'api_key = \"your_key\"' to [llm] section in config.toml, or\n"
            f"  2. Set environment variable: export {env_var}=your_api_key"
        )

    @property
    def label_marketing(self) -> str:
        """Label name for emails to unsubscribe from.

        This is an action label - applying it to any email will trigger
        unsubscription, whether applied by AI classification or manually by the user.
        """
        return self._get("labels", "marketing", default="Unsubscribe")

    @property
    def label_unsubscribed(self) -> str:
        """Label name for successfully unsubscribed emails."""
        return self._get("labels", "unsubscribed", default="Unsubscribed")

    @property
    def label_failed(self) -> str:
        """Label name for failed unsubscribe attempts."""
        return self._get("labels", "failed", default="Unsubscribe-Failed")

    @property
    def prompt_system(self) -> str:
        """System prompt for email classifier."""
        return self._get(
            "prompts",
            "system",
            default="You are an expert email analyst helping identify unwanted subscription emails.",
        )

    @property
    def prompt_marketing_criteria(self) -> str:
        """Criteria for identifying emails to unsubscribe from."""
        return self._get(
            "prompts",
            "marketing_criteria",
            default="Unwanted newsletters, promotional emails, marketing campaigns, spam-like notifications",
        )

    @property
    def prompt_exclusions(self) -> str:
        """What to exclude from unsubscribe suggestions."""
        return self._get(
            "prompts",
            "exclusions",
            default="Receipts, password resets, personal emails, banking alerts, wanted newsletters",
        )

    @property
    def prompt_user_preferences(self) -> str:
        """User-defined preferences for what emails to keep or avoid."""
        return self._get("prompts", "user_preferences", default="")

    @property
    def storage_state_file(self) -> str:
        """Path to state file for storing unsubscribe links."""
        default = str(get_state_file())
        return expand_path(self._get("storage", "state_file", default=default))

    @property
    def unsubscribe_headless(self) -> bool:
        """Whether to run browser in headless mode."""
        return self._get("unsubscribe", "headless", default=True)

    @property
    def unsubscribe_browser_timeout(self) -> int:
        """Browser operation timeout in seconds."""
        return self._get("unsubscribe", "browser_timeout", default=60)

    @property
    def unsubscribe_enable_mailto(self) -> bool:
        """Whether to enable mailto: unsubscribe via email sending."""
        return self._get("unsubscribe", "enable_mailto", default=True)

    # Browser automation model configuration
    # Allows using a different (specialized) model for browser automation

    @property
    def browser_provider(self) -> str | None:
        """LLM provider for browser automation.

        Options:
        - 'browser-use': Browser-Use's optimized model (fastest)
        - 'google': Gemini 2.5 Computer Use (specialized for UI)
        - 'anthropic': Claude 4.5 (excellent vision)
        - 'openai': GPT-5 (good general purpose)
        - None: Use same provider as classification (llm.provider)
        """
        return self._get("browser", "provider", default=None)

    @property
    def browser_model(self) -> str | None:
        """Model name for browser automation.

        Recommended models:
        - browser-use: (no model needed, uses their optimized model)
        - google: gemini-2.5-computer-use-preview-10-2025
        - anthropic: claude-4-5-sonnet
        - openai: gpt-5

        None uses the same model as classification (llm.model).
        """
        return self._get("browser", "model", default=None)

    @property
    def browser_api_key(self) -> str | None:
        """API key for browser automation model.

        Can be different from the classification API key.
        None uses the same key as classification (llm.api_key).
        """
        # First try config file
        config_key = self._get("browser", "api_key", default=None)
        if config_key:
            return config_key

        # Try environment variable
        env_var = self._get("browser", "api_key_env", default=None)
        if env_var:
            api_key = os.getenv(env_var)
            if api_key:
                return api_key

        # Check for BROWSER_USE_API_KEY if provider is browser-use
        provider = self._get("browser", "provider", default=None)
        if provider == "browser-use":
            api_key = os.getenv("BROWSER_USE_API_KEY")
            if api_key:
                return api_key

        return None  # Will fall back to llm_api_key
