"""Tests for the unsubscribe command's method selection and failure handling."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from gmail_ai_unsub.cli import main
from gmail_ai_unsub.unsubscribe.llm_errors import LLMUnavailableError

POST = "gmail_ai_unsub.unsubscribe.email_unsub.send_http_post_unsubscribe"
BROWSER = "gmail_ai_unsub.unsubscribe.browser_agent.unsubscribe_via_browser_sync"


def _headers(sender: str) -> list[dict[str, str]]:
    return [
        {"name": "Subject", "value": f"News from {sender}"},
        {"name": "From", "value": f"{sender} <news@{sender}.example>"},
        {"name": "List-Unsubscribe", "value": f"<https://{sender}.example/unsub>"},
        {"name": "List-Unsubscribe-Post", "value": "List-Unsubscribe=One-Click"},
    ]


@pytest.fixture
def env(tmp_path: Path) -> dict[str, Any]:
    """Config file, state file and a fake Gmail client holding two marketing emails."""
    state_file = tmp_path / "state.json"
    config_file = tmp_path / "config.toml"
    config_file.write_text(f'[storage]\nstate_file = "{state_file}"\n')

    senders = {"m1": "alpha", "m2": "beta"}
    client = MagicMock()
    client.labels.get_label_id.return_value = "L_MARKETING"
    client.labels.get_or_create_label.side_effect = lambda name: f"L_{name}"
    client.list_messages.return_value = {"messages": [{"id": m} for m in senders]}
    client.get_message_metadata.side_effect = lambda m: {
        "id": m,
        "internalDate": "1790000000000",
        "payload": {"headers": _headers(senders[m])},
    }
    client.get_message.side_effect = lambda m, format="full": {
        "id": m,
        "payload": {"headers": _headers(senders[m])},
    }
    return {"config": config_file, "state": state_file, "client": client}


def _run(env: dict[str, Any]) -> Any:
    with patch("gmail_ai_unsub.cli.GmailClient", return_value=env["client"]):
        return CliRunner().invoke(
            main, ["unsubscribe", "--yes", "--config", str(env["config"])], catch_exceptions=False
        )


def _links(env: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return json.loads(env["state"].read_text())["unsubscribe_links"]


def test_successful_one_click_post_counts_without_browser(env: dict[str, Any]) -> None:
    """An accepted RFC 8058 POST is a success even though no browser/LLM runs."""
    with patch(POST, return_value=True), patch(BROWSER) as browser:
        result = _run(env)

    assert result.exit_code == 0
    browser.assert_not_called()
    assert {link["status"] for link in _links(env).values()} == {"success"}
    # Each email moves from the marketing label to the unsubscribed label
    for call in env["client"].labels.apply_labels.call_args_list:
        assert call.kwargs["add_label_ids"] == ["L_Unsubscribed"]
        assert call.kwargs["remove_label_ids"] == ["L_MARKETING"]


def test_browser_failure_records_real_error(env: dict[str, Any]) -> None:
    """When POST fails and the browser fails too, the browser's error is stored."""
    with patch(POST, return_value=False), patch(BROWSER, return_value=(False, "Browser error: x")):
        result = _run(env)

    assert result.exit_code == 0
    links = _links(env)
    assert {link["status"] for link in links.values()} == {"failed"}
    assert {link["error"] for link in links.values()} == {"Browser error: x"}


def test_llm_unavailable_stops_run_and_leaves_emails_untouched(env: dict[str, Any]) -> None:
    """A dead LLM must not relabel or mark any email failed, and must stop the run."""
    with (
        patch(POST, return_value=False),
        patch(BROWSER, side_effect=LLMUnavailableError("402 prepayment credits depleted")) as b,
    ):
        result = _run(env)

    assert result.exit_code == 0
    assert "Browser LLM unavailable" in result.output
    assert b.call_count == 1  # second email never attempted
    env["client"].labels.apply_labels.assert_not_called()
    assert {link["status"] for link in _links(env).values()} == {"pending"}
