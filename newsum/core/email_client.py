import asyncio
import base64
import logging
import os
import random
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from core.models import RawEmail

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN_PATH = Path(os.path.expanduser("~/.credentials/gmail_token.json"))
MAX_RETRIES = 3


def _get_credentials() -> Credentials:
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            credentials_path = os.path.expanduser(
                os.getenv(
                    "GMAIL_CREDENTIALS_PATH", "~/.credentials/gmail_credentials.json"
                )
            )
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json())
    return creds


def run_auth_flow() -> None:
    """Standalone entry point for `python main.py --auth`."""
    _get_credentials()
    logger.info("Gmail OAuth flow complete. Token saved to %s", TOKEN_PATH)


def _extract_body(payload: dict) -> tuple[str, str | None]:
    """Returns (plain_text, html) extracted from a Gmail message payload."""
    plain_text = None
    html = None

    def walk(part: dict):
        nonlocal plain_text, html
        mime_type = part.get("mimeType", "")
        body_data = part.get("body", {}).get("data")
        if mime_type == "text/plain" and body_data and plain_text is None:
            plain_text = base64.urlsafe_b64decode(body_data).decode(
                "utf-8", errors="replace"
            )
        elif mime_type == "text/html" and body_data and html is None:
            html = base64.urlsafe_b64decode(body_data).decode(
                "utf-8", errors="replace"
            )
        for sub_part in part.get("parts", []):
            walk(sub_part)

    walk(payload)

    if plain_text:
        return plain_text, html
    if html:
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text(separator="\n", strip=True), html
    return "", html


def _header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


async def _get_with_retry(request_fn):
    for attempt in range(MAX_RETRIES):
        try:
            return await asyncio.to_thread(request_fn)
        except HttpError as exc:
            if exc.resp.status in (429, 500, 503) and attempt < MAX_RETRIES - 1:
                delay = (2**attempt) + random.uniform(0, 1)
                logger.warning(
                    "Gmail API error %s, retrying in %.1fs", exc.resp.status, delay
                )
                await asyncio.sleep(delay)
                continue
            logger.error("Gmail API call failed after retries: %s", exc)
            raise


async def fetch_emails(hours_back: int = 24) -> list[RawEmail]:
    creds = _get_credentials()
    service = build("gmail", "v1", credentials=creds)

    days = max(1, hours_back // 24) or 1
    query = f"newer_than:{days}d (category:updates OR category:promotions)"

    def list_messages():
        results = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=100)
            .execute()
        )
        return results.get("messages", [])

    message_refs = await _get_with_retry(list_messages)

    emails: list[RawEmail] = []
    for ref in message_refs:

        def get_message(msg_id=ref["id"]):
            return (
                service.users()
                .messages()
                .get(userId="me", id=msg_id, format="full")
                .execute()
            )

        try:
            msg = await _get_with_retry(get_message)
        except HttpError:
            continue

        headers = msg["payload"].get("headers", [])
        sender = _header(headers, "From")
        sender_domain = sender.split("@")[-1].rstrip(">").strip() if "@" in sender else ""
        subject = _header(headers, "Subject")
        has_unsubscribe = bool(_header(headers, "List-Unsubscribe"))
        body_text, body_html = _extract_body(msg["payload"])
        received_at = datetime.fromtimestamp(
            int(msg["internalDate"]) / 1000, tz=timezone.utc
        )

        emails.append(
            RawEmail(
                id=msg["id"],
                sender=sender,
                sender_domain=sender_domain,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
                received_at=received_at,
                has_unsubscribe_header=has_unsubscribe,
                labels=msg.get("labelIds", []),
            )
        )

    return emails
