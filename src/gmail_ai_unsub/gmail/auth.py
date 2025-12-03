"""Gmail API OAuth2 authentication.

This module handles OAuth2 authentication for the Gmail API. It supports:
1. Environment variables (GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET) - for development/CI
2. Embedded default credentials (for PyPI releases)
3. User-provided credentials.json file (for custom OAuth apps)

For open-source distribution:
- Credentials are loaded from environment variables first (for dev/CI)
- Fall back to embedded defaults (injected at build time for PyPI wheels)
- Users can provide their own credentials.json to use their own OAuth app

This follows the "public client" pattern for native/desktop apps where the
client_secret is treated as non-secret. Security comes from PKCE and user consent.

Gmail API Scopes used:
- gmail.readonly: Read email messages and metadata
- gmail.modify: Modify labels on messages
- gmail.send: Send emails (for mailto: unsubscribe)

See: https://developers.google.com/workspace/gmail/api/auth/scopes
"""

import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from gmail_ai_unsub.storage import expand_path

# Scopes required for the application
# See: https://developers.google.com/workspace/gmail/api/auth/scopes
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",  # Read emails and metadata
    "https://www.googleapis.com/auth/gmail.modify",  # Modify labels on messages
    "https://www.googleapis.com/auth/gmail.send",  # Send emails (for mailto unsubscribe)
]


def _get_client_credentials() -> tuple[str, str]:
    """Get OAuth2 client credentials from environment or embedded defaults.

    Priority:
    1. Environment variables (GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET) - for dev/CI
    2. Embedded defaults (injected at build time for PyPI wheels)

    Returns:
        Tuple of (client_id, client_secret)

    Note:
        For open-source native apps, the client_secret is treated as non-secret.
        Security comes from PKCE and user consent, not from hiding the secret.

        For development: Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET in .env
        For PyPI builds: Credentials are injected at build time via BUILD_* env vars
        For GitHub: Credentials are not in source, use GitHub secrets for CI
    """
    # Check environment variables first (for development and CI)
    # This allows overriding even in built wheels
    env_client_id = os.getenv("GMAIL_CLIENT_ID")
    env_client_secret = os.getenv("GMAIL_CLIENT_SECRET")

    if env_client_id and env_client_secret:
        return (env_client_id, env_client_secret)

    # Embedded defaults - these are injected at build time for PyPI wheels
    # In source tree, these are placeholders (not real credentials)
    # At build time, BUILD_GMAIL_CLIENT_ID and BUILD_GMAIL_CLIENT_SECRET
    # are used to replace these values before packaging
    _BUILD_CLIENT_ID = "__GMAIL_CLIENT_ID__"
    _BUILD_CLIENT_SECRET = "__GMAIL_CLIENT_SECRET__"

    # At build time, these get replaced if BUILD_* env vars are set
    # For now, use the values directly (they'll be in the wheel)
    return (_BUILD_CLIENT_ID, _BUILD_CLIENT_SECRET)


def get_default_client_config() -> dict:
    """Get the default OAuth2 client configuration.

    Loads credentials from environment variables or embedded defaults.

    Returns:
        OAuth2 client configuration dict in the format expected by
        google_auth_oauthlib.flow.InstalledAppFlow
    """
    client_id, client_secret = _get_client_credentials()
    return {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "redirect_uris": ["http://localhost"],
        }
    }


def get_credentials(
    credentials_file: str | None,
    token_file: str,
    use_default_credentials: bool = True,
) -> Credentials:
    """Get valid OAuth2 credentials for Gmail API.

    Raises:
        FileNotFoundError: If credentials file is not found
        ValueError: If credentials are invalid or OAuth flow fails

    Args:
        credentials_file: Path to OAuth2 client credentials JSON file.
            If None and use_default_credentials is True, uses embedded credentials.
        token_file: Path to store/load OAuth2 token
        use_default_credentials: If True and credentials_file doesn't exist,
            use the embedded default credentials.

    Returns:
        Valid Credentials object

    Raises:
        FileNotFoundError: If credentials_file doesn't exist and
            use_default_credentials is False
    """
    creds = None
    token_path = Path(expand_path(token_file))

    # Load existing token if available
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Determine which credentials to use
            creds_path = None
            if credentials_file:
                creds_path = Path(expand_path(credentials_file))

            if creds_path and creds_path.exists():
                # Use user-provided credentials file
                flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            elif use_default_credentials:
                # Use embedded default credentials
                flow = InstalledAppFlow.from_client_config(get_default_client_config(), SCOPES)
            else:
                raise FileNotFoundError(
                    f"Credentials file not found: {credentials_file}\n"
                    f"Please download it from: "
                    f"https://console.cloud.google.com/apis/credentials\n"
                    f"See docs/setup.md for detailed instructions."
                )

            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    if creds is None:
        raise ValueError("Failed to obtain credentials")
    return creds


def run_oauth_flow(token_file: str, credentials_file: str | None = None) -> bool:
    """Run the OAuth2 flow interactively and save the token.

    This function is designed to be called from the setup wizard to
    authenticate the user before they start using the tool.

    Args:
        token_file: Path to save the OAuth2 token
        credentials_file: Optional path to custom credentials.json

    Returns:
        True if authentication was successful, False otherwise
    """
    try:
        token_path = Path(expand_path(token_file))

        # Determine which credentials to use
        if credentials_file:
            creds_path = Path(expand_path(credentials_file))
            if creds_path.exists():
                flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            else:
                # Fall back to default credentials
                flow = InstalledAppFlow.from_client_config(get_default_client_config(), SCOPES)
        else:
            flow = InstalledAppFlow.from_client_config(get_default_client_config(), SCOPES)

        # Run the OAuth flow - this opens a browser
        creds = flow.run_local_server(port=0)

        # Save the token
        token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, "w", encoding="utf-8") as token:
            token.write(creds.to_json())

        return True

    except Exception:
        return False


def check_token_valid(token_file: str) -> bool:
    """Check if an existing token is valid.

    Args:
        token_file: Path to the token file

    Returns:
        True if token exists and is valid (or can be refreshed), False otherwise
    """
    token_path = Path(expand_path(token_file))

    if not token_path.exists():
        return False

    try:
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        if creds.valid:
            return True

        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Save refreshed token
            with open(token_path, "w", encoding="utf-8") as token:
                token.write(creds.to_json())
            return True

        return False

    except Exception:
        return False


def get_scopes_description() -> list[tuple[str, str]]:
    """Get human-readable descriptions of the required scopes.

    Returns:
        List of (scope_url, description) tuples
    """
    return [
        (
            "https://www.googleapis.com/auth/gmail.readonly",
            "Read your email messages and settings",
        ),
        (
            "https://www.googleapis.com/auth/gmail.modify",
            "Manage your email labels",
        ),
        (
            "https://www.googleapis.com/auth/gmail.send",
            "Send emails on your behalf (for unsubscribe requests)",
        ),
    ]
