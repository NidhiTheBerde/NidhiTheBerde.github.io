import json
from pathlib import Path

from core.models import RawEmail

DEFAULT_FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_emails.json"


async def fetch_emails(fixture_path: str | Path = DEFAULT_FIXTURE_PATH) -> list[RawEmail]:
    """Gmail substitute for end-to-end testing: loads RawEmail records from a JSON fixture
    instead of calling the Gmail API. Same return shape as core.email_client.fetch_emails."""
    data = json.loads(Path(fixture_path).read_text())
    return [RawEmail(**record) for record in data]
