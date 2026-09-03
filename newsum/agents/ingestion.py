import logging

from core.models import RawEmail
from core import email_client

logger = logging.getLogger(__name__)


async def fetch_emails(hours_back: int = 24) -> list[RawEmail]:
    """Layer 1: Authenticate with Gmail and fetch recent emails."""
    emails = await email_client.fetch_emails(hours_back=hours_back)
    logger.info("Fetched %d emails (hours_back=%d)", len(emails), hours_back)
    return emails
