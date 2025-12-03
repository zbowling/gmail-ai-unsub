"""Command-line interface for gmail-ai-unsub."""

from datetime import datetime, timedelta
from typing import Literal, cast

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from gmail_ai_unsub.cache import EmailCache
from gmail_ai_unsub.classifier.email_classifier import create_classifier
from gmail_ai_unsub.config import Config
from gmail_ai_unsub.gmail.client import GmailClient
from gmail_ai_unsub.storage import StateStorage
from gmail_ai_unsub.unsubscribe.extractor import (
    extract_list_unsubscribe_header,
    extract_unsubscribe_from_body,
    parse_email_body,
)

console = Console()


def get_gmail_url(message_id: str) -> str:
    """Generate a Gmail URL to open a message directly."""
    return f"https://mail.google.com/mail/u/0/#inbox/{message_id}"


def truncate_text(text: str, max_length: int) -> str:
    """Truncate text with ellipsis if too long."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 1] + "…"


def extract_email_address(from_header: str) -> str:
    """Extract just the email address from a From header."""
    # Handle formats like "Name <email@example.com>" or just "email@example.com"
    if "<" in from_header and ">" in from_header:
        start = from_header.index("<") + 1
        end = from_header.index(">")
        return from_header[start:end]
    return from_header.strip()


# Load environment variables from .env file
load_dotenv()


@click.group()
@click.version_option()
def main() -> None:
    """Gmail AI Unsubscribe Tool - AI-powered email management."""
    pass


@main.command()
@click.option(
    "--days",
    default=30,
    type=int,
    help="Number of days of emails to scan (default: 30)",
)
@click.option(
    "--label",
    default=None,
    help="Label name for marketing emails (default: from config)",
)
@click.option(
    "--scan-label",
    default=None,
    help="Label to scan (default: inbox only). Use 'inbox' for main inbox, or specify a label name.",
)
@click.option(
    "--config",
    type=click.Path(exists=True),
    help="Path to config.toml file",
)
@click.option(
    "--no-cache",
    is_flag=True,
    help="Ignore cache and re-analyze all emails",
)
def scan(
    days: int,
    label: str | None,
    scan_label: str | None,
    config: str | None,
    no_cache: bool,
) -> None:
    """Scan emails and label marketing emails."""
    try:
        cfg = Config(config) if config else Config()
        storage = StateStorage(cfg.storage_state_file)
        cache = EmailCache()
        client = GmailClient(cfg.gmail_credentials_file, cfg.gmail_token_file)

        # Use label from config if not provided
        marketing_label = label or cfg.label_marketing
        unsubscribed_label = cfg.label_unsubscribed
        failed_label = cfg.label_failed
        marketing_label_id = client.labels.get_or_create_label(marketing_label)

        # Create classifier
        classifier = create_classifier(
            provider=cast(Literal["google", "anthropic", "openai"], cfg.llm_provider),
            model=cfg.llm_model,
            api_key=cfg.llm_api_key,
            system_prompt=cfg.prompt_system,
            marketing_criteria=cfg.prompt_marketing_criteria,
            exclusions=cfg.prompt_exclusions,
            temperature=cfg.llm_temperature,
            thinking_level=cfg.llm_thinking_level,
            max_tokens=cfg.llm_max_tokens,
            user_preferences=cfg.prompt_user_preferences,
        )

        # Build query for emails in the specified time range
        # Exclude emails already labeled as Unsubscribe, Unsubscribed, or Unsubscribe-Failed
        after_date = (datetime.now() - timedelta(days=days)).strftime("%Y/%m/%d")

        # Build label exclusion - Gmail API uses label names as-is (with / for hierarchical)
        # Need to quote labels that might have special characters
        def escape_label_for_query(label_name: str) -> str:
            """Escape label name for Gmail query."""
            # Gmail labels with spaces or special chars should be quoted
            if " " in label_name or "/" in label_name:
                return f'"{label_name}"'
            return label_name

        exclude_labels = [
            f"-label:{escape_label_for_query(marketing_label)}",
            f"-label:{escape_label_for_query(unsubscribed_label)}",
            f"-label:{escape_label_for_query(failed_label)}",
        ]

        # Build location filter - default to inbox only
        location_filter = "in:inbox"
        if scan_label:
            if scan_label.lower() == "inbox":
                location_filter = "in:inbox"
            else:
                # User specified a label to scan
                location_filter = f"in:label:{escape_label_for_query(scan_label)}"

        query = f"after:{after_date} {location_filter} {' '.join(exclude_labels)}"

        # Get cache stats
        cache_stats = cache.get_stats()

        # Print header with configuration
        console.print()
        config_table = Table(show_header=False, box=None, padding=(0, 2))
        config_table.add_column("Key", style="dim")
        config_table.add_column("Value", style="cyan")
        config_table.add_row("Model", f"{cfg.llm_provider}/{cfg.llm_model}")
        params = []
        if cfg.llm_temperature is not None:
            params.append(f"temp={cfg.llm_temperature}")
        if cfg.llm_thinking_level is not None:
            params.append(f"thinking={cfg.llm_thinking_level}")
        if params:
            config_table.add_row("Parameters", ", ".join(params))
        config_table.add_row("Time Range", f"Last {days} days")
        scan_location = scan_label if scan_label else "inbox"
        config_table.add_row("Location", scan_location)
        config_table.add_row("Label", marketing_label)
        if no_cache:
            config_table.add_row("Cache", "[yellow]Disabled (--no-cache)[/yellow]")
        else:
            config_table.add_row(
                "Cache",
                f"{cache_stats['total']} emails cached ({cache_stats['marketing']} marketing)",
            )

        console.print(
            Panel(config_table, title="[bold]Scan Configuration[/bold]", border_style="blue")
        )
        console.print()

        # Process emails in batches
        page_token = None
        total_processed = 0
        total_marketing = 0
        total_errors = 0
        total_skipped = 0

        # Get terminal width for formatting
        term_width = console.width or 80

        while True:
            result = client.list_messages(query=query, max_results=50, page_token=page_token)
            messages = result.get("messages", [])

            if not messages:
                if total_processed == 0 and total_skipped == 0:
                    console.print("[yellow]No new emails to scan.[/yellow]")
                break

            # Filter out already-cached emails (batch lookup for efficiency)
            if not no_cache:
                all_ids = [msg["id"] for msg in messages]
                cached_ids = cache.get_analyzed_ids(all_ids)
                messages = [msg for msg in messages if msg["id"] not in cached_ids]
                total_skipped += len(cached_ids)

            for msg_ref in messages:
                message_id = msg_ref["id"]
                total_processed += 1

                try:
                    # Get message metadata first (quota-efficient)
                    message_meta = client.get_message_metadata(message_id)

                    # Extract headers
                    headers = message_meta.get("payload", {}).get("headers", [])
                    subject = ""
                    from_address = ""

                    for header in headers:
                        name = header.get("name", "").lower()
                        value = header.get("value", "")
                        if name == "subject":
                            subject = value
                        elif name == "from":
                            from_address = value

                    # Build display info
                    gmail_url = get_gmail_url(message_id)
                    email_addr = extract_email_address(from_address)

                    # Calculate available width for subject
                    # Account for: "  [123] Subject... " + padding
                    prefix_len = len(f"  [{total_processed}] ")
                    subject_width = max(20, term_width - prefix_len - 5)
                    display_subject = truncate_text(subject, subject_width)

                    # Show email being processed with spinner
                    with Progress(
                        SpinnerColumn("dots"),
                        TextColumn("[progress.description]{task.description}"),
                        console=console,
                        transient=True,
                    ) as progress:
                        task_desc = f"[bold]#{total_processed}[/bold] Analyzing..."
                        progress.add_task(task_desc, total=None)

                        # Get full message for body
                        message_full = client.get_message(message_id, format="full")
                        body, _ = parse_email_body(message_full)

                        # Classify email
                        result_class = classifier.classify_sync(subject, from_address, body)

                    # Display result
                    if result_class.is_marketing:
                        # Apply marketing label
                        client.labels.apply_label(message_id, marketing_label_id)
                        total_marketing += 1

                        # Build result display
                        result_text = Text()
                        result_text.append(f"  [{total_processed}] ", style="bold green")
                        result_text.append("✓ ", style="green")
                        result_text.append(display_subject, style="white")
                        console.print(result_text)

                        # Second line with details
                        detail_text = Text()
                        detail_text.append("       ", style="dim")
                        detail_text.append("From: ", style="dim")
                        detail_text.append(truncate_text(email_addr, 40), style="cyan")
                        detail_text.append("  Confidence: ", style="dim")
                        conf_color = "green" if result_class.confidence > 0.8 else "yellow"
                        detail_text.append(f"{result_class.confidence:.0%}", style=conf_color)
                        detail_text.append("  ", style="dim")
                        detail_text.append(gmail_url, style="dim underline link " + gmail_url)
                        console.print(detail_text)

                        # Extract unsubscribe link if available
                        unsubscribe_link = extract_list_unsubscribe_header(message_meta)
                        if not unsubscribe_link:
                            unsubscribe_link = extract_unsubscribe_from_body(body, message_id)

                        if unsubscribe_link:
                            storage.add_unsubscribe_link(unsubscribe_link)
                            console.print("       [dim green]↳ Unsubscribe link found[/dim green]")
                    else:
                        # Not marketing - show in dimmer style
                        result_text = Text()
                        result_text.append(f"  [{total_processed}] ", style="dim")
                        result_text.append("· ", style="dim")
                        result_text.append(display_subject, style="dim")
                        console.print(result_text)

                        detail_text = Text()
                        detail_text.append("       ", style="dim")
                        detail_text.append("From: ", style="dim")
                        detail_text.append(truncate_text(email_addr, 40), style="dim cyan")
                        detail_text.append("  Not marketing ", style="dim")
                        detail_text.append(f"({result_class.confidence:.0%})", style="dim")
                        console.print(detail_text)

                    # Cache the result (commits immediately to survive Ctrl+C)
                    cache.mark_analyzed(
                        email_id=message_id,
                        is_marketing=result_class.is_marketing,
                        confidence=result_class.confidence,
                        subject=subject[:200] if subject else None,
                        from_address=from_address[:200] if from_address else None,
                    )

                    console.print()  # Blank line between emails

                except Exception as e:
                    total_errors += 1
                    error_text = Text()
                    error_text.append(f"  [{total_processed}] ", style="bold red")
                    error_text.append("✗ ", style="red")
                    error_text.append(f"Error: {e}", style="red")
                    console.print(error_text)
                    console.print()
                    continue

            page_token = result.get("nextPageToken")
            if not page_token:
                break

        # Print summary
        console.print()
        summary_table = Table(show_header=False, box=None, padding=(0, 2))
        summary_table.add_column("Metric", style="dim")
        summary_table.add_column("Value", style="bold")
        summary_table.add_row("Total Scanned", str(total_processed))
        summary_table.add_row("Marketing Found", f"[green]{total_marketing}[/green]")
        if total_skipped > 0:
            summary_table.add_row("Skipped (cached)", f"[dim]{total_skipped}[/dim]")
        if total_errors > 0:
            summary_table.add_row("Errors", f"[red]{total_errors}[/red]")

        console.print(
            Panel(summary_table, title="[bold]Scan Complete[/bold]", border_style="green")
        )

        if total_marketing > 0:
            console.print()
            console.print(
                f"[dim]Run [cyan]gmail-unsub unsubscribe[/cyan] to unsubscribe from "
                f"{total_marketing} email{'s' if total_marketing != 1 else ''}.[/dim]"
            )

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise click.Abort() from None


@main.command()
@click.option(
    "--label",
    default=None,
    help="Label name for emails to unsubscribe from (default: from config)",
)
@click.option(
    "--headless/--no-headless",
    default=None,
    help="Run browser in headless mode (default: from config)",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompts (unsubscribe from all)",
)
@click.option(
    "--config",
    type=click.Path(exists=True),
    help="Path to config.toml file",
)
def unsubscribe(label: str | None, headless: bool | None, yes: bool, config: str | None) -> None:
    """Unsubscribe from labeled marketing emails.

    Interactively prompts for each email unless --yes is passed.
    """
    import questionary
    from rich.rule import Rule

    try:
        cfg = Config(config) if config else Config()
        storage = StateStorage(cfg.storage_state_file)
        client = GmailClient(cfg.gmail_credentials_file, cfg.gmail_token_file)

        marketing_label = label or cfg.label_marketing

        # Get label IDs - use fuzzy matching to find existing, only create if needed
        marketing_label_id = client.labels.get_label_id(marketing_label)
        if not marketing_label_id:
            console.print(
                f"[yellow]Label '{marketing_label}' not found. No emails to process.[/yellow]"
            )
            return

        # These we create if they don't exist
        unsubscribed_label_id = client.labels.get_or_create_label(cfg.label_unsubscribed)
        failed_label_id = client.labels.get_or_create_label(cfg.label_failed)

        # Get all emails with the marketing label
        query = f"label:{marketing_label.replace('/', '-')}"

        console.print()
        console.print(f"[bold]Finding emails with label:[/bold] [cyan]{marketing_label}[/cyan]")

        # Collect all messages with metadata
        emails_to_process = []
        page_token = None

        with Progress(
            SpinnerColumn("dots"),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task("Loading emails...", total=None)

            while True:
                result = client.list_messages(query=query, max_results=50, page_token=page_token)
                messages = result.get("messages", [])

                for msg in messages:
                    message_id = msg["id"]
                    # Get metadata for display
                    message_meta = client.get_message_metadata(message_id)
                    headers = message_meta.get("payload", {}).get("headers", [])

                    subject = ""
                    from_address = ""
                    date_header = ""
                    for header in headers:
                        name = header.get("name", "").lower()
                        value = header.get("value", "")
                        if name == "subject":
                            subject = value
                        elif name == "from":
                            from_address = value
                        elif name == "date":
                            date_header = value

                    # Extract email date - prefer internalDate (Unix timestamp in ms), fallback to Date header
                    email_date = datetime.now()  # Default to now if we can't parse
                    if message_meta.get("internalDate"):
                        try:
                            # Gmail internalDate is Unix timestamp in milliseconds
                            email_date = datetime.fromtimestamp(
                                int(message_meta["internalDate"]) / 1000
                            )
                        except (ValueError, TypeError):
                            pass
                    elif date_header:
                        try:
                            from email.utils import parsedate_to_datetime

                            email_date = parsedate_to_datetime(date_header)
                        except (ValueError, TypeError):
                            pass

                    # Get unsubscribe link
                    unsub_link = storage.get_unsubscribe_link(message_id)
                    if not unsub_link:
                        unsub_link = extract_list_unsubscribe_header(message_meta)
                        if not unsub_link:
                            message_full = client.get_message(message_id, format="full")
                            body, html = parse_email_body(message_full)
                            unsub_link = extract_unsubscribe_from_body(body, message_id, html)
                        if unsub_link:
                            storage.add_unsubscribe_link(unsub_link)

                    emails_to_process.append(
                        {
                            "id": message_id,
                            "subject": subject,
                            "from": from_address,
                            "email": extract_email_address(from_address),
                            "link": unsub_link,
                            "gmail_url": get_gmail_url(message_id),
                            "date": email_date,
                        }
                    )

                page_token = result.get("nextPageToken")
                if not page_token:
                    break

        if not emails_to_process:
            console.print("[yellow]No emails found with that label.[/yellow]")
            return

        console.print(f"[bold]Found {len(emails_to_process)} emails to process[/bold]")
        console.print()

        # Process each email
        success_count = 0
        failed_count = 0
        skipped_count = 0
        auto_yes = yes  # Track if user selected "Always"

        for i, email in enumerate(emails_to_process, 1):
            message_id = email["id"]
            unsub_link = email["link"]
            from_address = email["from"]
            email_date = email["date"]

            # Check if we've already unsubscribed from this sender
            if not storage.should_unsubscribe_from_sender(from_address, email_date):
                last_unsub_date = storage.get_last_unsubscribed_date(from_address)
                if last_unsub_date:
                    console.print(
                        f"[dim]Skipping {email['subject'][:50]}... - already unsubscribed from {extract_email_address(from_address)} on {last_unsub_date.strftime('%Y-%m-%d')}[/dim]"
                    )
                    skipped_count += 1
                    continue

            # Display email info
            console.print(Rule(f"[bold]Email {i}/{len(emails_to_process)}[/bold]"))
            console.print()

            info_table = Table(show_header=False, box=None, padding=(0, 2))
            info_table.add_column("Field", style="dim", width=12)
            info_table.add_column("Value")

            info_table.add_row("Subject", truncate_text(email["subject"], 60))
            info_table.add_row("From", email["from"])
            info_table.add_row("Gmail", f"[link={email['gmail_url']}]{email['gmail_url']}[/link]")

            # Show unsubscribe method
            if unsub_link:
                if unsub_link.list_unsubscribe_header:
                    method = "[green]Header (RFC 8058)[/green]"
                    if unsub_link.mailto_address:
                        method += f" → mailto:{unsub_link.mailto_address}"
                    elif unsub_link.link_url:
                        method += f" → {truncate_text(unsub_link.link_url, 50)}"
                elif unsub_link.link_url:
                    method = f"[yellow]Browser[/yellow] → {truncate_text(unsub_link.link_url, 50)}"
                elif unsub_link.mailto_address:
                    method = f"[cyan]Email[/cyan] → {unsub_link.mailto_address}"
                else:
                    method = "[red]None found[/red]"
                info_table.add_row("Method", method)
            else:
                info_table.add_row("Method", "[red]No unsubscribe link found[/red]")

            console.print(info_table)
            console.print()

            # Handle missing unsubscribe link
            if not unsub_link:
                console.print("[red]✗ Skipping - no unsubscribe method available[/red]")
                failed_count += 1
                client.labels.apply_labels(
                    message_id,
                    add_label_ids=[failed_label_id],
                    remove_label_ids=[marketing_label_id],
                )
                storage.update_link_status(message_id, "failed", "No unsubscribe link found")
                console.print()
                continue

            # Ask for confirmation unless auto_yes
            if not auto_yes:
                choice = questionary.select(
                    "Unsubscribe from this sender?",
                    choices=[
                        questionary.Choice("Yes", value="yes"),
                        questionary.Choice("No (skip)", value="no"),
                        questionary.Choice("Always (don't ask again)", value="always"),
                        questionary.Choice("Quit", value="quit"),
                    ],
                ).ask()

                if choice is None or choice == "quit":
                    console.print("[dim]Quitting...[/dim]")
                    break
                elif choice == "no":
                    console.print("[dim]Skipped[/dim]")
                    skipped_count += 1
                    console.print()
                    continue
                elif choice == "always":
                    auto_yes = True

            # Attempt unsubscribe - try ALL available methods for maximum success
            try:
                headless_mode = headless if headless is not None else cfg.unsubscribe_headless
                success = False
                error = None
                message_full = client.get_message(message_id, format="full")

                # Strategy: Attack from all fronts!
                # 1. Send mailto email if available (RFC 8058)
                # 2. Try RFC 8058 POST if URL supports one-click
                # 3. Always use browser automation for URLs (verifies/completes the process)

                mailto_success = False

                # Step 1: Try mailto unsubscribe (if available)
                if unsub_link.mailto_address and cfg.unsubscribe_enable_mailto:
                    console.print("[cyan]Sending unsubscribe email (mailto)...[/cyan]")

                    with Progress(
                        SpinnerColumn("dots"),
                        TextColumn("[progress.description]{task.description}"),
                        console=console,
                        transient=True,
                    ) as progress:
                        progress.add_task("Sending email...", total=None)

                        from gmail_ai_unsub.unsubscribe.email_unsub import (
                            send_mailto_unsubscribe,
                        )

                        mailto_success = send_mailto_unsubscribe(
                            client, unsub_link.mailto_address, message_full
                        )

                        if mailto_success:
                            console.print("[dim]✓ Unsubscribe email sent[/dim]")
                        else:
                            console.print("[dim]✗ Mailto failed (will try other methods)[/dim]")

                # Step 2: Try RFC 8058 POST if URL supports one-click
                if unsub_link.link_url:
                    # Check if it supports one-click POST
                    headers = message_full.get("payload", {}).get("headers", [])
                    has_one_click = False
                    for header in headers:
                        if (
                            header.get("name", "").lower() == "list-unsubscribe-post"
                            and "List-Unsubscribe=One-Click" in header.get("value", "")
                        ):
                            has_one_click = True
                            break

                    if has_one_click:
                        console.print("[cyan]Trying RFC 8058 one-click POST...[/cyan]")

                        with Progress(
                            SpinnerColumn("dots"),
                            TextColumn("[progress.description]{task.description}"),
                            console=console,
                            transient=True,
                        ) as progress:
                            progress.add_task("Sending POST...", total=None)

                            from gmail_ai_unsub.unsubscribe.email_unsub import (
                                send_http_post_unsubscribe,
                            )

                            post_success = send_http_post_unsubscribe(
                                unsub_link.link_url, message_full
                            )

                            if post_success:
                                console.print("[dim]✓ POST request sent[/dim]")
                            else:
                                console.print("[dim]✗ POST failed (will try browser)[/dim]")

                # Step 3: Always use browser automation for URLs
                # This verifies the unsubscribe worked and handles any additional steps
                if unsub_link.link_url:
                    from gmail_ai_unsub.unsubscribe.extractor import (
                        extract_all_unsubscribe_urls_from_body,
                        test_url_accessibility,
                        validate_url,
                    )

                    # Collect all possible URLs to try
                    urls_to_try = []

                    # Start with header URL if valid
                    header_url = unsub_link.link_url
                    if validate_url(header_url):
                        urls_to_try.append(header_url)

                    # Extract all URLs from email body (HTML parsing with BeautifulSoup)
                    body_text, html_content = parse_email_body(message_full)
                    body_urls = extract_all_unsubscribe_urls_from_body(body_text, html_content)

                    # Add body URLs that aren't already in the list
                    for body_url in body_urls:
                        if body_url not in urls_to_try:
                            urls_to_try.append(body_url)

                    if not urls_to_try:
                        console.print(
                            "[yellow]⚠ No valid unsubscribe URLs found (header invalid, body search found nothing)[/yellow]"
                        )
                    elif len(urls_to_try) > 1:
                        console.print(
                            f"[cyan]Found {len(urls_to_try)} unsubscribe URLs, will try each until one works...[/cyan]"
                        )

                    # Try each URL until one succeeds
                    for i, url_to_try in enumerate(urls_to_try, 1):
                        if len(urls_to_try) > 1:
                            console.print(
                                f"[dim]Trying URL {i}/{len(urls_to_try)}: {truncate_text(url_to_try, 60)}[/dim]"
                            )

                        # Quick accessibility check (skip if we're already trying it)
                        if i > 1:  # Don't check first URL, just try it
                            is_accessible, status_code = test_url_accessibility(url_to_try)
                            if not is_accessible and status_code == 404:
                                console.print(
                                    f"[dim]  ⚠ URL {i} returned 404, trying next...[/dim]"
                                )
                                continue

                        if headless_mode:
                            console.print(
                                "[cyan]Launching browser (headless) to verify/complete...[/cyan]"
                            )
                        else:
                            console.print(
                                "[cyan]Launching browser (incognito) to verify/complete...[/cyan]"
                            )

                        from gmail_ai_unsub.unsubscribe.browser_agent import (
                            unsubscribe_via_browser_sync,
                        )

                        success, error = unsubscribe_via_browser_sync(
                            url_to_try,
                            cfg,
                            headless=headless_mode,
                            timeout=cfg.unsubscribe_browser_timeout,
                            incognito=True,
                        )

                        if success:
                            # Update stored link with the working URL
                            unsub_link.link_url = url_to_try
                            storage.add_unsubscribe_link(unsub_link)
                            break  # Success! Stop trying other URLs
                        elif error:
                            if len(urls_to_try) > 1:
                                console.print(
                                    f"[yellow]  ⚠ URL {i} failed: {error}, trying next...[/yellow]"
                                )
                            else:
                                console.print(f"[yellow]Browser note: {error}[/yellow]")
                    else:
                        # Tried all URLs, none worked
                        if len(urls_to_try) > 1:
                            console.print("[red]✗ All unsubscribe URLs failed[/red]")
                elif unsub_link.mailto_address:
                    # Only mailto available - consider it success if email was sent
                    success = mailto_success

                # Update labels and status
                if success:
                    console.print("[green]✓ Successfully unsubscribed[/green]")
                    client.labels.apply_labels(
                        message_id,
                        add_label_ids=[unsubscribed_label_id],
                        remove_label_ids=[marketing_label_id],
                    )
                    storage.update_link_status(message_id, "success")
                    # Record successful unsubscribe for this sender
                    storage.record_unsubscribed_sender(from_address, email_date)
                    success_count += 1
                else:
                    console.print("[red]✗ Failed to unsubscribe[/red]")
                    client.labels.apply_labels(
                        message_id,
                        add_label_ids=[failed_label_id],
                        remove_label_ids=[marketing_label_id],
                    )
                    storage.update_link_status(message_id, "failed", "Unsubscribe attempt failed")
                    failed_count += 1

            except Exception as e:
                console.print(f"[red]✗ Error: {e}[/red]")
                failed_count += 1
                storage.update_link_status(message_id, "failed", str(e))

            console.print()

        # Print summary
        console.print(Rule("[bold]Summary[/bold]"))
        console.print()

        summary_table = Table(show_header=False, box=None, padding=(0, 2))
        summary_table.add_column("Metric", style="dim")
        summary_table.add_column("Value", style="bold")
        summary_table.add_row("Successful", f"[green]{success_count}[/green]")
        summary_table.add_row("Failed", f"[red]{failed_count}[/red]")
        if skipped_count > 0:
            summary_table.add_row("Skipped", f"[yellow]{skipped_count}[/yellow]")

        console.print(
            Panel(summary_table, title="[bold]Unsubscribe Complete[/bold]", border_style="green")
        )

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise click.Abort() from None


@main.command()
@click.option(
    "--config",
    type=click.Path(exists=True),
    help="Path to config.toml file",
)
def status(config: str | None) -> None:
    """Show status of unsubscribe attempts."""
    try:
        cfg = Config(config) if config else Config()
        storage = StateStorage(cfg.storage_state_file)

        all_links = storage.get_all_links()
        pending = [link for link in all_links if link.status == "pending"]
        success = [link for link in all_links if link.status == "success"]
        failed = [link for link in all_links if link.status == "failed"]

        click.echo("Unsubscribe Status:")
        click.echo(f"  Total: {len(all_links)}")
        click.echo(f"  Pending: {len(pending)}")
        click.echo(f"  Successful: {len(success)}")
        click.echo(f"  Failed: {len(failed)}")

        if pending:
            click.echo("\nPending unsubscribe links:")
            for link in pending[:10]:  # Show first 10
                click.echo(f"  - {link.email_id}: {link.link_url or link.mailto_address}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort() from None


@main.command()
def setup() -> None:
    """Interactive setup wizard to configure gmail-ai-unsub.

    Updates existing config or creates a new one. Your current settings
    will be prefilled so you can easily update specific options.
    """
    from gmail_ai_unsub.setup.wizard import run_setup_wizard

    success = run_setup_wizard()
    if not success:
        raise click.Abort() from None


@main.group()
def cache() -> None:
    """Manage the email analysis cache.

    The cache stores which emails have been analyzed to avoid re-processing
    and save API tokens. Use these commands to view stats or clear the cache.
    """
    pass


@cache.command(name="stats")
def cache_stats() -> None:
    """Show cache statistics."""
    from gmail_ai_unsub.cache import EmailCache, get_cache_db_path

    email_cache = EmailCache()
    stats = email_cache.get_stats()
    db_path = get_cache_db_path()

    console.print()
    stats_table = Table(show_header=False, box=None, padding=(0, 2))
    stats_table.add_column("Metric", style="dim")
    stats_table.add_column("Value", style="cyan")
    stats_table.add_row("Total Cached", str(stats["total"]))
    stats_table.add_row("Marketing", f"[green]{stats['marketing']}[/green]")
    stats_table.add_row("Not Marketing", f"[dim]{stats['non_marketing']}[/dim]")
    stats_table.add_row("Database", str(db_path))

    # Get file size
    if db_path.exists():
        size_bytes = db_path.stat().st_size
        if size_bytes < 1024:
            size_str = f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            size_str = f"{size_bytes / 1024:.1f} KB"
        else:
            size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
        stats_table.add_row("Size", size_str)

    console.print(Panel(stats_table, title="[bold]Cache Statistics[/bold]", border_style="blue"))


@cache.command(name="clear")
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompt",
)
def cache_clear(yes: bool) -> None:
    """Clear the email analysis cache.

    This will cause all emails to be re-analyzed on the next scan.
    Use this if you've manually changed labels and want to re-process emails.
    """
    from gmail_ai_unsub.cache import EmailCache

    email_cache = EmailCache()
    stats = email_cache.get_stats()

    if stats["total"] == 0:
        console.print("[yellow]Cache is already empty.[/yellow]")
        return

    if not yes:
        console.print(f"[yellow]This will clear {stats['total']} cached email analyses.[/yellow]")
        if not click.confirm("Are you sure you want to continue?"):
            console.print("[dim]Cancelled.[/dim]")
            return

    count = email_cache.clear()
    email_cache.vacuum()  # Reclaim disk space
    console.print(f"[green]✓[/green] Cleared {count} cached entries.")


@cache.command(name="remove")
@click.argument("email_id")
def cache_remove(email_id: str) -> None:
    """Remove a specific email from the cache.

    Use this to re-analyze a single email on the next scan.
    """
    from gmail_ai_unsub.cache import EmailCache

    email_cache = EmailCache()

    if email_cache.remove(email_id):
        console.print(f"[green]✓[/green] Removed {email_id} from cache.")
    else:
        console.print(f"[yellow]Email {email_id} was not in cache.[/yellow]")


if __name__ == "__main__":
    main()
