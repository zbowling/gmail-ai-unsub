"""Tests for Gmail OAuth credential handling."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from google.auth.exceptions import RefreshError

from gmail_ai_unsub.gmail.auth import get_credentials


def _expired_creds(refresh_error: Exception | None = None) -> MagicMock:
    creds = MagicMock()
    creds.valid = False
    creds.expired = True
    creds.refresh_token = "refresh-token"
    if refresh_error:
        creds.refresh.side_effect = refresh_error
    return creds


def _token_file(tmp_path: Path) -> Path:
    token_file = tmp_path / "token.json"
    token_file.write_text("{}")
    return token_file


def test_refresh_error_falls_back_to_oauth_flow(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An invalid_grant refresh failure should trigger a fresh OAuth flow."""
    token_file = _token_file(tmp_path)
    new_creds = MagicMock()
    new_creds.to_json.return_value = '{"token": "new"}'

    with (
        patch(
            "gmail_ai_unsub.gmail.auth.Credentials.from_authorized_user_file",
            return_value=_expired_creds(RefreshError("invalid_grant: Bad Request")),
        ),
        patch("gmail_ai_unsub.gmail.auth.InstalledAppFlow") as flow_cls,
    ):
        flow_cls.from_client_config.return_value.run_local_server.return_value = new_creds
        creds = get_credentials(None, str(token_file))

    assert creds is new_creds
    assert token_file.read_text() == '{"token": "new"}'
    assert "re-authorizing" in capsys.readouterr().err


def test_retryable_refresh_error_is_raised(tmp_path: Path) -> None:
    """Transient refresh failures must not discard the token or start a login."""
    token_file = _token_file(tmp_path)

    with (
        patch(
            "gmail_ai_unsub.gmail.auth.Credentials.from_authorized_user_file",
            return_value=_expired_creds(RefreshError("server error", retryable=True)),
        ),
        patch("gmail_ai_unsub.gmail.auth.InstalledAppFlow") as flow_cls,
        pytest.raises(RefreshError),
    ):
        get_credentials(None, str(token_file))

    flow_cls.from_client_config.assert_not_called()


def test_successful_refresh_skips_oauth_flow(tmp_path: Path) -> None:
    """A working refresh token should be used without any interactive login."""
    token_file = _token_file(tmp_path)
    creds_in = _expired_creds()
    creds_in.refresh.side_effect = lambda _request: setattr(creds_in, "valid", True)
    creds_in.to_json.return_value = '{"token": "refreshed"}'

    with (
        patch(
            "gmail_ai_unsub.gmail.auth.Credentials.from_authorized_user_file",
            return_value=creds_in,
        ),
        patch("gmail_ai_unsub.gmail.auth.InstalledAppFlow") as flow_cls,
    ):
        creds = get_credentials(None, str(token_file))

    assert creds is creds_in
    creds_in.refresh.assert_called_once()
    flow_cls.from_client_config.assert_not_called()
    assert token_file.read_text() == '{"token": "refreshed"}'
