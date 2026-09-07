import asyncio
import logging
from pathlib import Path

from core.database import Database
from core.llm_client import LLMClient
from core.models import ClassifiedNewsletter, ExtractedInsight

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "extract.txt"

CHUNK_TOKENS = 4000
CHUNK_OVERLAP_TOKENS = 500
CHARS_PER_TOKEN = 4  # rough heuristic, no tokenizer dependency
CHUNK_THRESHOLD_TOKENS = 6000


def _chunk_text(text: str) -> list[str]:
    chunk_chars = CHUNK_TOKENS * CHARS_PER_TOKEN
    overlap_chars = CHUNK_OVERLAP_TOKENS * CHARS_PER_TOKEN
    if len(text) <= CHUNK_THRESHOLD_TOKENS * CHARS_PER_TOKEN:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_chars, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap_chars
    return chunks


def _dedupe_insights(insights: list[dict]) -> list[dict]:
    """Deduplicate near-identical insight points using normalized text overlap."""
    seen: list[set[str]] = []
    unique: list[dict] = []
    for insight in insights:
        words = set(insight["point"].lower().split())
        is_dupe = False
        for seen_words in seen:
            if not words or not seen_words:
                continue
            overlap = len(words & seen_words) / len(words | seen_words)
            if overlap > 0.7:
                is_dupe = True
                break
        if not is_dupe:
            seen.append(words)
            unique.append(insight)
    return unique


async def extract_insights(
    classified: ClassifiedNewsletter,
    llm: LLMClient,
    db: Database,
) -> list[ExtractedInsight]:
    """Layer 3: Extract 3-5 atomic key insights from a single newsletter."""
    email = classified.email
    prompt_template = PROMPT_PATH.read_text()
    chunks = _chunk_text(email.body_text)

    all_insights: list[dict] = []
    for chunk in chunks:
        prompt = prompt_template.format(
            sender=email.sender,
            subject=email.subject,
            category=classified.category,
            date=email.received_at.isoformat(),
            body_text=chunk,
        )
        try:
            result = await llm.complete_json(
                system="You extract atomic, factual insights from newsletters.",
                user=prompt,
                max_tokens=1000,
            )
            all_insights.extend(result.get("insights", []))
        except Exception as exc:
            logger.warning(
                "Extraction failed for %s (%s): %s", email.id, email.subject, exc
            )

    if len(chunks) > 1:
        all_insights = _dedupe_insights(all_insights)

    insights = []
    for item in all_insights:
        insight = ExtractedInsight(
            newsletter_id=email.id,
            sender=email.sender,
            subject=email.subject,
            point=item["point"],
            importance=int(item.get("importance", 3)),
            topic_tags=item.get("topic_tags", []),
            category=classified.category,
        )
        await db.save_insight(
            email_id=email.id,
            category=classified.category,
            point=insight.point,
            importance=insight.importance,
            topic_tags=insight.topic_tags,
        )
        insights.append(insight)

    return insights


async def extract_all(
    classified_newsletters: list[ClassifiedNewsletter],
    llm: LLMClient,
    db: Database,
) -> list[ExtractedInsight]:
    """Run extraction concurrently across all newsletters in a category."""
    results = await asyncio.gather(
        *[extract_insights(c, llm, db) for c in classified_newsletters],
        return_exceptions=True,
    )
    insights: list[ExtractedInsight] = []
    for r in results:
        if isinstance(r, Exception):
            logger.warning("Extraction task failed: %s", r)
            continue
        insights.extend(r)
    return insights
