"""Extract unsubscribe links and headers from emails."""

import base64
import re
from email.header import decode_header
from quopri import decodestring
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from gmail_ai_unsub.storage import UnsubscribeLink


def decode_mime_header(header_value: str) -> str:
    """Decode MIME-encoded header value.

    Args:
        header_value: Raw header value

    Returns:
        Decoded string
    """
    decoded_parts = decode_header(header_value)
    decoded_str = ""
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            decoded_str += part.decode(encoding or "utf-8", errors="replace")
        else:
            decoded_str += part
    return decoded_str


def validate_url(url: str) -> bool:
    """Validate that a URL looks complete and is likely to work.

    Checks for common signs of truncated or malformed URLs:
    - Ends with incomplete query parameters (e.g., `?envelope=`)
    - Missing path or domain
    - Looks truncated

    Args:
        url: URL to validate

    Returns:
        True if URL looks valid, False if it appears truncated/malformed
    """
    if not url:
        return False

    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return False

    # Check for truncated query parameters (common issue with Action Network)
    # URLs ending with `=` or `?` are likely incomplete
    if url.rstrip().endswith("=") or url.rstrip().endswith("?"):
        return False

    # Check if query string looks incomplete (ends with `=` without a value)
    if parsed.query and parsed.query.rstrip().endswith("="):
        return False

    return True


def test_url_accessibility(url: str, timeout: int = 5) -> tuple[bool, int | None]:
    """Test if a URL is accessible (not 404).

    Args:
        url: URL to test
        timeout: Request timeout in seconds

    Returns:
        Tuple of (is_accessible: bool, status_code: int | None)
    """
    try:
        response = requests.head(url, timeout=timeout, allow_redirects=True)
        # Consider 2xx, 3xx as accessible, 4xx/5xx as not accessible
        is_accessible = 200 <= response.status_code < 400
        return (is_accessible, response.status_code)
    except Exception:
        # If request fails, assume URL might still work (could be network issue)
        # Return True to give it a chance
        return (True, None)


def extract_list_unsubscribe_header(message: dict[str, Any]) -> UnsubscribeLink | None:
    """Extract List-Unsubscribe header from Gmail message.

    Args:
        message: Gmail API message dict (metadata format)

    Returns:
        UnsubscribeLink if found, None otherwise
    """
    headers = message.get("payload", {}).get("headers", [])
    list_unsubscribe = None

    for header in headers:
        name = header.get("name", "").lower()
        value = header.get("value", "")

        if name == "list-unsubscribe":
            list_unsubscribe = value

    if not list_unsubscribe:
        return None

    # Parse the header value - can contain multiple URLs (comma or angle bracket separated)
    # Format: <https://example.com/unsub>, <mailto:unsub@example.com>
    urls = []
    mailto_addresses = []

    # Extract URLs from angle brackets
    url_pattern = r"<([^>]+)>"
    matches = re.findall(url_pattern, list_unsubscribe)
    for match in matches:
        # Remove spaces (common issue with malformed headers like Office Depot)
        match = match.replace(" ", "")
        if match.startswith("mailto:"):
            mailto_addresses.append(match[7:])  # Remove "mailto:" prefix
        elif match.startswith("http://") or match.startswith("https://"):
            urls.append(match)

    # Also check for URLs not in angle brackets
    if not matches:
        # Try to find URLs directly
        # Remove spaces first (handle malformed headers)
        list_unsubscribe_clean = list_unsubscribe.replace(" ", "")
        url_pattern = r"(https?://[^\s,>]+|mailto:[^\s,>]+)"
        direct_matches = re.findall(url_pattern, list_unsubscribe_clean)
        for match in direct_matches:
            if match.startswith("mailto:"):
                mailto_addresses.append(match[7:])
            else:
                urls.append(match)

    email_id = message["id"]

    # Prefer URL over mailto if both exist
    if urls:
        return UnsubscribeLink(
            email_id=email_id,
            link_url=urls[0],
            mailto_address=mailto_addresses[0] if mailto_addresses else None,
            list_unsubscribe_header=list_unsubscribe,
            source="header",
            status="pending",
            error=None,
        )
    elif mailto_addresses:
        return UnsubscribeLink(
            email_id=email_id,
            link_url=None,
            mailto_address=mailto_addresses[0],
            list_unsubscribe_header=list_unsubscribe,
            source="header",
            status="pending",
            error=None,
        )

    return None


def decode_quoted_printable(text: str) -> str:
    """Decode quoted-printable encoded text.

    Args:
        text: Quoted-printable encoded text

    Returns:
        Decoded text
    """
    try:
        # quopri.decodestring expects bytes
        if isinstance(text, str):
            text_bytes = text.encode("utf-8", errors="replace")
        else:
            text_bytes = text

        decoded_bytes = decodestring(text_bytes)
        return decoded_bytes.decode("utf-8", errors="replace")
    except Exception:
        return text


def extract_all_unsubscribe_links_from_html(html_content: str, email_id: str) -> list[str]:
    """Extract all unsubscribe links from HTML email using BeautifulSoup.

    Looks for <a> tags with unsubscribe-related text or hrefs.

    Args:
        html_content: HTML email content
        email_id: Gmail message ID

    Returns:
        List of unsubscribe URLs found
    """
    urls = []
    try:
        soup = BeautifulSoup(html_content, "html.parser")

        # Find all <a> tags
        for link in soup.find_all("a", href=True):
            href_raw = link.get("href", "")
            # BeautifulSoup can return href as string, list, or None
            if isinstance(href_raw, list):
                href = str(href_raw[0]) if href_raw else ""
            elif href_raw is None:
                href = ""
            else:
                href = str(href_raw)

            link_text = link.get_text(strip=True).lower()

            # Check if href or link text contains unsubscribe keywords
            unsubscribe_keywords = [
                "unsubscribe",
                "unsub",
                "opt-out",
                "optout",
                "remove",
                "preferences",
            ]

            href_lower = href.lower()
            is_unsubscribe = any(keyword in href_lower for keyword in unsubscribe_keywords) or any(
                keyword in link_text for keyword in unsubscribe_keywords
            )

            if is_unsubscribe:
                # Clean and validate URL
                url = href.strip()
                # Remove spaces (common issue with malformed URLs)
                url = url.replace(" ", "")

                # Validate it's a proper URL
                parsed = urlparse(url)
                if parsed.scheme in ("http", "https") and validate_url(url):
                    if url not in urls:  # Avoid duplicates
                        urls.append(url)

    except Exception:
        # If BeautifulSoup fails, fall back to regex
        pass

    return urls


def extract_unsubscribe_from_body(
    body_text: str, email_id: str, html_content: str | None = None
) -> UnsubscribeLink | None:
    """Extract unsubscribe link(s) from email body.

    Tries multiple methods:
    1. BeautifulSoup parsing of HTML (if available)
    2. Regex patterns for HTML hrefs
    3. Regex patterns for plain text URLs

    Args:
        body_text: Email body text (plain text or HTML)
        email_id: Gmail message ID
        html_content: Raw HTML content (if available, for better parsing)

    Returns:
        UnsubscribeLink with the first valid URL found, or None
    """
    urls = []

    # Method 1: Use BeautifulSoup if we have HTML content
    if html_content:
        # Decode quoted-printable if needed
        html_decoded = decode_quoted_printable(html_content)
        urls.extend(extract_all_unsubscribe_links_from_html(html_decoded, email_id))

    # Method 2: Regex patterns for HTML hrefs (fallback)
    if not urls:
        html_patterns = [
            r'href=["\']([^"\']*unsub[^"\']*)["\']',
            r'href=["\']([^"\']*unsubscribe[^"\']*)["\']',
            r'href=["\']([^"\']*opt.?out[^"\']*)["\']',
        ]

        for pattern in html_patterns:
            matches = re.findall(pattern, body_text, re.IGNORECASE)
            for match in matches:
                url = match.rstrip(".,;:!?)").replace(" ", "")  # Remove spaces
                parsed = urlparse(url)
                if parsed.scheme in ("http", "https") and validate_url(url):
                    if url not in urls:
                        urls.append(url)

    # Method 3: Plain text URL patterns (last resort)
    if not urls:
        text_patterns = [
            r'(https?://[^\s<>"]*unsub[^\s<>"]*)',
            r'(https?://[^\s<>"]*unsubscribe[^\s<>"]*)',
            r'(https?://[^\s<>"]*opt.?out[^\s<>"]*)',
        ]

        for pattern in text_patterns:
            matches = re.findall(pattern, body_text, re.IGNORECASE)
            for match in matches:
                url = match.rstrip(".,;:!?)").replace(" ", "")  # Remove spaces
                parsed = urlparse(url)
                if parsed.scheme in ("http", "https") and validate_url(url):
                    if url not in urls:
                        urls.append(url)

    # Return the first valid URL found
    if urls:
        return UnsubscribeLink(
            email_id=email_id,
            link_url=urls[0],  # Store first URL in link_url
            mailto_address=None,
            list_unsubscribe_header=None,
            source="body",
            status="pending",
            error=None,
        )

    return None


def extract_all_unsubscribe_urls_from_body(
    body_text: str, html_content: str | None = None
) -> list[str]:
    """Extract ALL unsubscribe URLs from email body.

    Returns a list of all found URLs (not just the first one).

    Args:
        body_text: Email body text
        html_content: Raw HTML content (if available)

    Returns:
        List of unsubscribe URLs
    """
    urls = []

    # Use BeautifulSoup if we have HTML
    if html_content:
        html_decoded = decode_quoted_printable(html_content)
        urls.extend(extract_all_unsubscribe_links_from_html(html_decoded, ""))

    # Also try regex patterns
    patterns = [
        r'href=["\']([^"\']*unsub[^"\']*)["\']',
        r'href=["\']([^"\']*unsubscribe[^"\']*)["\']',
        r'href=["\']([^"\']*opt.?out[^"\']*)["\']',
        r'(https?://[^\s<>"]*unsub[^\s<>"]*)',
        r'(https?://[^\s<>"]*unsubscribe[^\s<>"]*)',
        r'(https?://[^\s<>"]*opt.?out[^\s<>"]*)',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, body_text, re.IGNORECASE)
        for match in matches:
            url = match.rstrip(".,;:!?)").replace(" ", "")  # Remove spaces
            parsed = urlparse(url)
            if parsed.scheme in ("http", "https") and validate_url(url):
                if url not in urls:
                    urls.append(url)

    return urls


def parse_email_body(message: dict[str, Any]) -> tuple[str, str | None]:
    """Extract plain text and HTML body from Gmail message.

    Handles quoted-printable encoding and base64 decoding.

    Args:
        message: Gmail API message dict (full format)

    Returns:
        Tuple of (plain_text_body, html_content)
    """
    plain_text = ""
    html_content = None

    def extract_from_part(part: dict[str, Any]) -> tuple[str, str | None]:
        """Recursively extract text and HTML from message part."""
        text_body = ""
        html_body = None
        mime_type = part.get("mimeType", "")
        encoding = part.get("body", {}).get("encoding", "").lower()

        if mime_type == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                try:
                    # Decode based on encoding
                    if encoding == "base64":
                        decoded_bytes = base64.urlsafe_b64decode(data)
                    elif encoding == "quoted-printable":
                        decoded_bytes = decodestring(data.encode("utf-8", errors="replace"))
                    else:
                        # Assume base64 for Gmail API
                        decoded_bytes = base64.urlsafe_b64decode(data)

                    text_body = decoded_bytes.decode("utf-8", errors="replace")
                except Exception:
                    pass

        elif mime_type == "text/html":
            data = part.get("body", {}).get("data", "")
            if data:
                try:
                    # Decode based on encoding
                    if encoding == "base64":
                        decoded_bytes = base64.urlsafe_b64decode(data)
                    elif encoding == "quoted-printable":
                        decoded_bytes = decodestring(data.encode("utf-8", errors="replace"))
                    else:
                        # Assume base64 for Gmail API
                        decoded_bytes = base64.urlsafe_b64decode(data)

                    html_body = decoded_bytes.decode("utf-8", errors="replace")

                    # Also extract text from HTML for plain text version
                    from html import unescape

                    text = re.sub(r"<[^>]+>", "", html_body)
                    text_body = unescape(text)
                except Exception:
                    pass

        # Check for multipart
        if "parts" in part:
            for subpart in part["parts"]:
                sub_text, sub_html = extract_from_part(subpart)
                text_body += sub_text
                if sub_html and not html_body:
                    html_body = sub_html

        return (text_body, html_body)

    payload = message.get("payload", {})
    plain_text, html_content = extract_from_part(payload)

    return (plain_text, html_content)
