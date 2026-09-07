from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class RawEmail(BaseModel):
    id: str
    sender: str
    sender_domain: str
    subject: str
    body_text: str
    body_html: Optional[str] = None
    received_at: datetime
    has_unsubscribe_header: bool
    labels: list[str]


class ClassifiedNewsletter(BaseModel):
    email: RawEmail
    is_newsletter: bool
    category: str  # matches a key in filters.yaml
    confidence: float  # 0.0-1.0
    classification_reason: str


class ExtractedInsight(BaseModel):
    newsletter_id: str
    sender: str
    subject: str
    point: str  # The extracted fact/claim/event
    importance: int  # 1-5
    topic_tags: list[str]
    category: str


class SummaryPoint(BaseModel):
    rank: int
    headline: str  # One punchy sentence
    detail: str  # Why it matters (1-2 sentences)
    sources: list[str]  # Sender names that covered this
    category: str


class DailySummary(BaseModel):
    date: str
    category: str
    points: list[SummaryPoint]  # Up to 10
    newsletters_processed: int
    generated_at: datetime
