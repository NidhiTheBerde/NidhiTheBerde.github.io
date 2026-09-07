import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from core.llm_client import LLMClient
from core.models import DailySummary, ExtractedInsight, SummaryPoint

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "aggregate.txt"


async def aggregate_category(
    category: str,
    insights: list[ExtractedInsight],
    llm: LLMClient,
    date: str | None = None,
) -> DailySummary | None:
    """Layer 4: Synthesize up to 10 ranked, non-redundant summary points."""
    if not insights:
        logger.info("No newsletters matched category '%s', skipping aggregation", category)
        return None

    date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    senders = {i.sender for i in insights}

    insights_payload = [
        {
            "sender": i.sender,
            "subject": i.subject,
            "point": i.point,
            "importance": i.importance,
            "topic_tags": i.topic_tags,
        }
        for i in insights
    ]

    prompt_template = PROMPT_PATH.read_text()
    prompt = prompt_template.format(
        n=len(senders),
        category=category,
        date=date,
        insights_json=json.dumps(insights_payload, indent=2),
    )

    try:
        result = await llm.complete_json(
            system="You synthesize cross-source intelligence into a ranked brief.",
            user=prompt,
            max_tokens=3000,
        )
    except Exception as exc:
        logger.error("Aggregation failed for category '%s': %s", category, exc)
        return None

    raw_points = result.get("summary_points", [])
    if not raw_points:
        logger.info("Aggregation for '%s' returned zero points", category)

    points = [
        SummaryPoint(
            rank=p.get("rank", idx + 1),
            headline=p["headline"],
            detail=p["detail"],
            sources=p.get("sources", []),
            category=category,
        )
        for idx, p in enumerate(raw_points[:10])
    ]

    return DailySummary(
        date=date,
        category=category,
        points=points,
        newsletters_processed=len(senders),
        generated_at=datetime.now(timezone.utc),
    )
