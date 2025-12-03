"""Interactive setup wizard using Rich and Questionary.

This module provides a beautiful, data-driven TUI for configuring gmail-ai-unsub.
The wizard is generated from the schema definitions, making it easy to maintain
and extend without hardcoding prompts.
"""

import os
import sys
from pathlib import Path
from typing import Any

import questionary
from questionary import Choice as QChoice
from questionary import Style
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from gmail_ai_unsub.gmail.auth import (
    check_token_valid,
    get_scopes_description,
    run_oauth_flow,
)
from gmail_ai_unsub.paths import (
    get_config_dir,
    get_config_file,
    get_data_dir,
    get_state_dir,
    get_state_file,
    get_token_file,
)
from gmail_ai_unsub.setup.schema import (
    ANTHROPIC_MODELS,
    GOOGLE_MODELS,
    OPENAI_MODELS,
    ConfigField,
    ConfigSection,
    FieldType,
    build_config_schema,
    get_api_key_env_for_provider,
    get_api_key_url,
    get_provider_name,
)

# Rich console for beautiful output
console = Console()

# Custom questionary style matching our theme
WIZARD_STYLE = Style(
    [
        ("qmark", "fg:cyan bold"),
        ("question", "bold"),
        ("answer", "fg:cyan"),
        ("pointer", "fg:cyan bold"),
        ("highlighted", "fg:cyan bold"),
        ("selected", "fg:green"),
        ("separator", "fg:gray"),
        ("instruction", "fg:gray italic"),
        ("text", ""),
        ("disabled", "fg:gray italic"),
    ]
)


def clear_screen() -> None:
    """Clear the terminal screen."""
    console.clear()


def print_header() -> None:
    """Print the wizard header."""
    header = Text()
    header.append("Gmail AI Unsubscribe", style="bold cyan")
    header.append(" - Setup Wizard", style="dim")

    console.print()
    console.print(Panel(header, border_style="cyan", padding=(0, 2)))
    console.print()


def print_section_header(section: ConfigSection) -> None:
    """Print a section header."""
    title = f"{section.icon}  {section.title}"
    console.print()
    console.print(Panel(title, border_style="blue", padding=(0, 1)))
    if section.description:
        console.print(f"  [dim]{section.description}[/dim]")
    console.print()


def print_paths_info() -> None:
    """Print information about where files will be stored."""
    config_dir = get_config_dir()
    data_dir = get_data_dir()
    state_dir = get_state_dir()

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Type", style="cyan")
    table.add_column("Path", style="dim")

    table.add_row("Config", str(config_dir))
    table.add_row("Data", str(data_dir))
    table.add_row("State", str(state_dir))

    console.print(Panel(table, title="📁 File Locations", border_style="dim"))
    console.print()


def prompt_field(field: ConfigField, current_values: dict[str, Any]) -> Any:
    """Prompt for a single field value.

    Args:
        field: The field definition
        current_values: Current configuration values (for conditional logic)

    Returns:
        The user's input value
    """
    # Check if field should be shown
    if field.show_if and not field.show_if(current_values):
        return None

    # Build the prompt message
    message = field.label
    if field.help_text:
        console.print(f"  [dim italic]{field.help_text}[/dim italic]")

    match field.field_type:
        case FieldType.SELECT:
            if not field.choices:
                return field.default

            choices = [
                QChoice(
                    title=f"{c.label}" + (f" - {c.description}" if c.description else ""),
                    value=c.value,
                )
                for c in field.choices
            ]

            return questionary.select(
                message,
                choices=choices,
                default=field.default,
                style=WIZARD_STYLE,
            ).ask()

        case FieldType.CONFIRM:
            return questionary.confirm(
                message,
                default=field.default if field.default is not None else True,
                style=WIZARD_STYLE,
            ).ask()

        case FieldType.TEXT:
            return questionary.text(
                message,
                default=str(field.default) if field.default else "",
                style=WIZARD_STYLE,
            ).ask()

        case FieldType.PATH:
            return questionary.path(
                message,
                default=str(field.default) if field.default else "",
                style=WIZARD_STYLE,
            ).ask()

        case FieldType.FLOAT:
            while True:
                result = questionary.text(
                    message,
                    default=str(field.default) if field.default is not None else "",
                    style=WIZARD_STYLE,
                ).ask()

                if result is None:
                    return None

                try:
                    value = float(result)
                    if field.min_value is not None and value < field.min_value:
                        console.print(f"  [red]Value must be >= {field.min_value}[/red]")
                        continue
                    if field.max_value is not None and value > field.max_value:
                        console.print(f"  [red]Value must be <= {field.max_value}[/red]")
                        continue
                    return value
                except ValueError:
                    console.print("  [red]Please enter a valid number[/red]")

        case FieldType.INT:
            while True:
                result = questionary.text(
                    message,
                    default=str(field.default) if field.default is not None else "",
                    style=WIZARD_STYLE,
                ).ask()

                if result is None:
                    return None

                try:
                    value = int(result)
                    if field.min_value is not None and value < field.min_value:
                        console.print(f"  [red]Value must be >= {int(field.min_value)}[/red]")
                        continue
                    if field.max_value is not None and value > field.max_value:
                        console.print(f"  [red]Value must be <= {int(field.max_value)}[/red]")
                        continue
                    return value
                except ValueError:
                    console.print("  [red]Please enter a valid integer[/red]")

        case FieldType.PASSWORD:
            return questionary.password(
                message,
                style=WIZARD_STYLE,
            ).ask()

    return field.default


def prompt_section(
    section: ConfigSection,
    current_values: dict[str, Any],
    skip_advanced: bool = False,
) -> dict[str, Any]:
    """Prompt for all fields in a section.

    Args:
        section: The section definition
        current_values: Current configuration values
        skip_advanced: Whether to skip advanced sections

    Returns:
        Dictionary of field key -> value
    """
    if section.advanced and skip_advanced:
        # Return defaults for advanced sections
        return {field.key: field.default for field in section.fields}

    print_section_header(section)

    values: dict[str, Any] = {}
    for field in section.fields:
        value = prompt_field(field, {**current_values, **values})
        if value is not None:
            values[field.key] = value
        elif field.default is not None:
            values[field.key] = field.default

    return values


def update_dynamic_choices(
    schema: list[ConfigSection],
    values: dict[str, Any],
) -> None:
    """Update dynamic choices based on current values.

    This handles things like updating the model list when the provider changes.
    """
    provider = values.get("llm.provider", "google")

    # Update model choices
    model_choices = {
        "google": GOOGLE_MODELS,
        "anthropic": ANTHROPIC_MODELS,
        "openai": OPENAI_MODELS,
    }.get(provider, GOOGLE_MODELS)

    # Find and update the fields
    for section in schema:
        for field in section.fields:
            if field.key == "llm.model":
                field.choices = model_choices
                # Update default to first model of new provider
                field.default = model_choices[0].value if model_choices else None
            elif field.key == "llm.api_key_env":
                field.default = get_api_key_env_for_provider(provider)


def generate_toml(values: dict[str, Any], paths: dict[str, str]) -> str:
    """Generate TOML configuration from values.

    Args:
        values: Dictionary of field key -> value
        paths: Dictionary of path names -> values

    Returns:
        TOML configuration string
    """
    lines = [
        "# Gmail AI Unsubscribe Configuration",
        "# Generated by: gmail-unsub setup",
        f"# Location: {paths['config_file']}",
        "#",
        "# Directory locations (platform-specific):",
        f"#   Config: {paths['config_dir']}",
        f"#   Data:   {paths['data_dir']}",
        f"#   State:  {paths['state_dir']}",
        "",
    ]

    # Group values by section
    sections: dict[str, dict[str, Any]] = {}
    for key, value in values.items():
        if value is None:
            continue
        parts = key.split(".", 1)
        if len(parts) == 2:
            section, field = parts
            if section not in sections:
                sections[section] = {}
            sections[section][field] = value

    # Generate TOML for each section
    section_order = ["gmail", "llm", "labels", "storage", "unsubscribe", "prompts"]
    for section_name in section_order:
        if section_name not in sections:
            continue

        lines.append(f"[{section_name}]")
        for field_name, value in sections[section_name].items():
            if isinstance(value, bool):
                lines.append(f"{field_name} = {str(value).lower()}")
            elif isinstance(value, int | float):
                lines.append(f"{field_name} = {value}")
            elif isinstance(value, str):
                # Escape quotes in strings
                escaped = value.replace('"', '\\"')
                lines.append(f'{field_name} = "{escaped}"')
        lines.append("")

    return "\n".join(lines)


def print_summary(values: dict[str, Any]) -> None:
    """Print a summary of the configuration."""
    console.print()
    console.print(Panel("📋 Configuration Summary", border_style="green"))
    console.print()

    table = Table(show_header=True, header_style="bold cyan", box=None)
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="white")

    # Key settings to show
    key_settings = [
        ("llm.provider", "Provider"),
        ("llm.model", "Model"),
        ("llm.api_key", "API Key"),
        ("llm.temperature", "Temperature"),
        ("llm.thinking_level", "Reasoning Mode"),
        ("labels.marketing", "Unsubscribe Label"),
        ("unsubscribe.headless", "Headless Mode"),
    ]

    for key, label in key_settings:
        value = values.get(key)
        if value is not None:
            if isinstance(value, bool):
                value = "Yes" if value else "No"
            elif key == "llm.api_key":
                # Mask API key for display
                value = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
            table.add_row(label, str(value))

    # Show if using env var for API key
    if "llm.api_key" not in values or values.get("llm.api_key") is None:
        env_var = values.get("llm.api_key_env", "GOOGLE_API_KEY")
        table.add_row("API Key", f"[dim](from {env_var} env var)[/dim]")

    console.print(table)


def print_gmail_scopes() -> None:
    """Print the Gmail API scopes we'll request."""
    console.print()
    console.print(Panel("🔐 Gmail Permissions Required", border_style="yellow"))
    console.print()
    console.print("  This tool needs the following Gmail permissions:")
    console.print()

    scopes = get_scopes_description()
    for _scope_url, description in scopes:
        console.print(f"  • {description}")

    console.print()
    console.print("  [dim]Your credentials are stored locally and never sent to any server.[/dim]")
    console.print()


def run_gmail_oauth(token_file: str, credentials_file: str | None = None) -> bool:
    """Run the Gmail OAuth flow with user feedback.

    Args:
        token_file: Path to save the OAuth token
        credentials_file: Optional path to custom credentials.json

    Returns:
        True if authentication was successful, False otherwise
    """
    # Check if already authenticated
    if check_token_valid(token_file):
        console.print()
        console.print("[green]✓[/green] Gmail is already authenticated!")
        if not questionary.confirm(
            "Re-authenticate with Gmail?",
            default=False,
            style=WIZARD_STYLE,
        ).ask():
            return True

    # Show what permissions we'll request
    print_gmail_scopes()

    # Confirm before opening browser
    if not questionary.confirm(
        "Open browser to authenticate with Gmail?",
        default=True,
        style=WIZARD_STYLE,
    ).ask():
        console.print(
            "[dim]Gmail authentication skipped. You can run 'gmail-unsub setup' later.[/dim]"
        )
        return False

    console.print()
    console.print("[cyan]Opening browser for Gmail authentication...[/cyan]")
    console.print("[dim]Please sign in and grant the requested permissions.[/dim]")
    console.print()

    # Run the OAuth flow
    success = run_oauth_flow(token_file, credentials_file)

    if success:
        console.print("[green]✓[/green] Gmail authentication successful!")
        return True
    else:
        console.print("[red]✗[/red] Gmail authentication failed.")
        console.print("[dim]You can try again by running 'gmail-unsub setup'[/dim]")
        return False


def collect_api_key(
    provider: str, existing_config: dict[str, Any] | None = None
) -> tuple[str | None, bool]:
    """Collect API key from user, checking existing config and env vars first.

    Args:
        provider: The LLM provider (google, anthropic, openai)
        existing_config: Existing config values (to prefill API key)

    Returns:
        Tuple of (api_key or None, save_to_config: bool)
        - api_key: The API key entered by user, or from env var
        - save_to_config: True if should save to config.toml, False if using env var
    """
    import webbrowser

    env_var = get_api_key_env_for_provider(provider)
    provider_name = get_provider_name(provider)
    api_key_url = get_api_key_url(provider)

    # Check for existing API key in config
    existing_config_key = None
    if existing_config:
        existing_config_key = existing_config.get("llm.api_key")

    # Check if API key is already set in environment
    existing_env_key = os.getenv(env_var)

    console.print()
    console.print(Panel(f"🔑 {provider_name} API Key", border_style="yellow"))
    console.print()

    # Priority: config > env var
    if existing_config_key:
        # Mask the key for display
        masked = (
            existing_config_key[:8] + "..." + existing_config_key[-4:]
            if len(existing_config_key) > 12
            else "***"
        )
        console.print("  [green]✓[/green] Found existing API key in config.toml")
        console.print(f"    [dim]{masked}[/dim]")
        console.print()

        use_existing = questionary.confirm(
            "Keep the existing API key from config.toml?",
            default=True,
            style=WIZARD_STYLE,
        ).ask()

        if use_existing:
            # User wants to keep the existing key
            return existing_config_key, True

    elif existing_env_key:
        # Mask the key for display
        masked = (
            existing_env_key[:8] + "..." + existing_env_key[-4:]
            if len(existing_env_key) > 12
            else "***"
        )
        console.print(f"  [green]✓[/green] Found existing API key in [cyan]{env_var}[/cyan]")
        console.print(f"    [dim]{masked}[/dim]")
        console.print()

        use_env = questionary.confirm(
            f"Use the API key from {env_var} environment variable?",
            default=True,
            style=WIZARD_STYLE,
        ).ask()

        if use_env:
            # User wants to use the env var, don't save to config
            return None, False

    # Need to collect API key from user
    console.print(f"  You need an API key from {provider_name}.")
    console.print(f"  [dim]URL: {api_key_url}[/dim]")
    console.print()

    if questionary.confirm(
        f"Open {provider_name} in your browser to get an API key?",
        default=True,
        style=WIZARD_STYLE,
    ).ask():
        console.print()
        console.print(f"  [cyan]Opening {api_key_url}...[/cyan]")
        webbrowser.open(api_key_url)
        console.print("  [dim]Create or copy your API key, then paste it below.[/dim]")
        console.print()

    # Ask for the API key
    # Note: questionary.password doesn't support default, so we'll handle it differently
    if existing_config_key:
        console.print(
            f"  [dim]Current key in config: {existing_config_key[:8]}...{existing_config_key[-4:]}[/dim]"
        )
        console.print(
            "  [dim]Press Enter without typing to keep it, or enter a new key to replace it.[/dim]"
        )
        console.print()

    api_key = questionary.password(
        f"Enter your {provider_name} API key"
        + (" (or press Enter to keep existing)" if existing_config_key else ":")
        + ":",
        style=WIZARD_STYLE,
    ).ask()

    # If user pressed Enter without typing and we have an existing key, keep it
    if existing_config_key and (not api_key or not api_key.strip()):
        console.print()
        console.print("[green]✓[/green] Keeping existing API key from config.toml")
        return existing_config_key, True

    if not api_key or not api_key.strip():
        console.print()
        console.print("[yellow]⚠[/yellow] No API key provided.")
        console.print(
            f"  [dim]You'll need to set {env_var} environment variable before using the tool.[/dim]"
        )
        return None, False

    api_key = api_key.strip()

    # Ask where to save
    console.print()
    save_choice = questionary.select(
        "Where should the API key be saved?",
        choices=[
            QChoice(
                title="Save to config.toml (recommended)",
                value="config",
            ),
            QChoice(
                title=f"I'll set {env_var} environment variable myself",
                value="env",
            ),
        ],
        style=WIZARD_STYLE,
    ).ask()

    if save_choice == "config":
        console.print()
        console.print("[green]✓[/green] API key will be saved to config.toml")
        console.print(
            "  [dim]Note: Keep your config.toml private and don't commit it to version control.[/dim]"
        )
        return api_key, True
    else:
        console.print()
        if sys.platform == "win32":
            cmd = f"set {env_var}={api_key}"
        else:
            cmd = f"export {env_var}={api_key}"
        console.print(f"  Run this command: [cyan]{cmd}[/cyan]")
        console.print("  [dim]Add it to your shell profile to make it permanent.[/dim]")
        return None, False


def print_next_steps(gmail_authenticated: bool) -> None:
    """Print next steps after setup."""
    console.print()
    console.print(Panel("🚀 Next Steps", border_style="cyan"))
    console.print()

    steps = []
    step_num = 1

    if not gmail_authenticated:
        steps.append(f"{step_num}. Authenticate with Gmail:\n   [cyan]gmail-unsub setup[/cyan]")
        step_num += 1

    steps.append(f"{step_num}. Scan your emails:\n   [cyan]gmail-unsub scan --days 30[/cyan]")
    step_num += 1

    steps.append(
        f"{step_num}. Review labeled emails in Gmail, then unsubscribe:\n   [cyan]gmail-unsub unsubscribe[/cyan]"
    )

    for step in steps:
        console.print(f"  {step}")
        console.print()


def load_existing_config(config_file: Path) -> dict[str, Any]:
    """Load existing config values from TOML file.

    Args:
        config_file: Path to config.toml

    Returns:
        Dictionary of field keys to values (e.g., {"llm.provider": "google"})
    """
    if not config_file.exists():
        return {}

    try:
        import tomllib

        with open(config_file, "rb") as f:
            data = tomllib.load(f)

        # Flatten nested structure to dot notation
        existing: dict[str, Any] = {}
        for section, section_data in data.items():
            if isinstance(section_data, dict):
                for key, value in section_data.items():
                    existing[f"{section}.{key}"] = value

        return existing
    except Exception:
        # If we can't load it, just return empty dict
        return {}


def prefill_schema_defaults(schema: list[ConfigSection], existing_values: dict[str, Any]) -> None:
    """Update schema field defaults with existing config values.

    Args:
        schema: Configuration schema
        existing_values: Existing config values from TOML
    """
    for section in schema:
        for field in section.fields:
            if field.key in existing_values:
                # Update the default to the existing value
                field.default = existing_values[field.key]


def run_setup_wizard(force: bool = False) -> bool:
    """Run the interactive setup wizard.

    Updates existing config or creates new one. Prefills questions with
    existing values if config already exists.

    Args:
        force: Whether to ignore existing config (unused, kept for compatibility)

    Returns:
        True if setup completed successfully, False otherwise
    """
    # Get platform-specific paths
    config_dir = get_config_dir()
    config_file = get_config_file()
    data_dir = get_data_dir()
    state_dir = get_state_dir()
    token_file = get_token_file()
    state_file = get_state_file()

    paths = {
        "config_dir": str(config_dir),
        "config_file": str(config_file),
        "data_dir": str(data_dir),
        "state_dir": str(state_dir),
        "token_file": str(token_file),
        "state_file": str(state_file),
    }

    # Load existing config values if config exists
    existing_values = load_existing_config(config_file)
    if existing_values:
        console.print()
        console.print(f"[green]Found existing config at:[/green] {config_file}")
        console.print(
            "[dim]Your current settings will be prefilled. Press Enter to keep them.[/dim]"
        )
        console.print()

    # Clear screen and show header
    clear_screen()
    print_header()
    print_paths_info()

    # Build the schema
    schema = build_config_schema(
        config_dir=str(config_dir),
        data_dir=str(data_dir),
        state_dir=str(state_dir),
        token_file=str(token_file),
        state_file=str(state_file),
    )

    # Prefill defaults with existing values
    prefill_schema_defaults(schema, existing_values)

    # Ask if user wants to customize advanced settings (only for truly advanced sections)
    # Note: prompts section is at the end and always shown (not advanced)
    customize_advanced = questionary.confirm(
        "Would you like to customize advanced settings (Gmail API, storage, advanced LLM)?",
        default=False,
        style=WIZARD_STYLE,
    ).ask()

    if customize_advanced is None:
        return False

    # Collect all values
    all_values: dict[str, Any] = {}

    for section in schema:
        # Update dynamic choices based on current values
        update_dynamic_choices(schema, all_values)

        # Prompt for section
        section_values = prompt_section(
            section,
            all_values,
            skip_advanced=not customize_advanced,
        )

        if section_values is None:
            return False

        all_values.update(section_values)

        # Special handling: update model choices after provider selection
        if section.key == "llm" and "llm.provider" in section_values:
            update_dynamic_choices(schema, all_values)

    # Get the selected provider
    provider = all_values.get("llm.provider", "google")

    # Collect API key for the provider, passing existing config to prefill
    api_key, save_to_config = collect_api_key(provider, existing_values)

    # Store API key in config values if user wants to save it
    if api_key and save_to_config:
        all_values["llm.api_key"] = api_key
    elif api_key is None and save_to_config is False:
        # User chose to use env var - don't save to config, but preserve existing if it exists
        # (don't add it to all_values, so it won't be written to TOML)
        pass

    # Always store the env var name as fallback
    all_values["llm.api_key_env"] = get_api_key_env_for_provider(provider)

    # Show summary
    print_summary(all_values)

    # Confirm before saving
    console.print()
    if not questionary.confirm(
        "Save this configuration?",
        default=True,
        style=WIZARD_STYLE,
    ).ask():
        console.print("[dim]Setup cancelled.[/dim]")
        return False

    # Create directories
    config_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)

    # Generate and write TOML
    toml_content = generate_toml(all_values, paths)
    config_file.write_text(toml_content)

    # Success message
    console.print()
    console.print(Panel("✅ Configuration saved successfully!", border_style="green"))
    console.print(f"  [dim]Location: {config_file}[/dim]")

    # Gmail OAuth authentication
    console.print()
    console.print(Panel("📧 Gmail Authentication", border_style="blue"))
    console.print()
    console.print("  Now let's connect to your Gmail account.")
    console.print()

    # Get the token file path (use the one from config if customized, otherwise default)
    actual_token_file = all_values.get("gmail.token_file", str(token_file))
    credentials_file = all_values.get("gmail.credentials_file")

    # Run Gmail OAuth
    gmail_authenticated = run_gmail_oauth(actual_token_file, credentials_file)

    # Next steps
    print_next_steps(gmail_authenticated)

    return True
