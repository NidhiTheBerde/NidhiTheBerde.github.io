import logging
from pathlib import Path

from core.database import Database
from core.llm_client import LLMClient
from core.models import ClassifiedNewsletter, RawEmail

logger = logging.getLogger(__name__)

KNOWN_NEWSLETTER_PLATFORMS = {
    "substack.com",
    "beehiiv.com",
    "mailchimp.com",
    "convertkit.com",
    "ghost.io",
    "buttondown.email",
}

SUBJECT_KEYWORDS = [
    "newsletter",
    "digest",
    "weekly",
    "roundup",
    "briefing",
    "issue #",
]

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "classify.txt"


def _heuristic_is_newsletter(email: RawEmail) -> bool:
    if email.has_unsubscribe_header:
        return True
    if any(email.sender_domain.endswith(d) for d in KNOWN_NEWSLETTER_PLATFORMS):
        return True
    subject_lower = email.subject.lower()
    if any(kw in subject_lower for kw in SUBJECT_KEYWORDS):
        return True
    return False


def _keyword_category_guess(email: RawEmail, filters: list[dict]) -> str | None:
    text = f"{email.subject} {email.body_text[:1000]}".lower()
    best_category = None
    best_hits = 0
    for f in filters:
        hits = sum(1 for kw in f.get("keywords", []) if kw.lower() in text)
        if hits > best_hits:
            best_hits = hits
            best_category = f["name"]
    return best_category


async def classify_email(
    email: RawEmail,
    filters: list[dict],
    llm: LLMClient,
    min_confidence: float = 0.7,
) -> ClassifiedNewsletter:
    """Layer 2: Determine whether an email is a newsletter and its category."""
    is_newsletter_heuristic = _heuristic_is_newsletter(email)

    if is_newsletter_heuristic:
        category = _keyword_category_guess(email, filters) or "none"
        if category != "none":
            return ClassifiedNewsletter(
                email=email,
                is_newsletter=True,
                category=category,
                confidence=1.0,
                classification_reason="Matched newsletter heuristic + keyword category",
            )

    categories = [f["name"] for f in filters]
    prompt_template = PROMPT_PATH.read_text()
    prompt = prompt_template.format(
        categories=", ".join(categories),
        sender=email.sender,
        subject=email.subject,
        body_preview=email.body_text[:500],
    )

    try:
        result = await llm.complete_json(
            system="You are a precise email classification assistant.",
            user=prompt,
            max_tokens=300,
        )
    except Exception as exc:
        logger.warning("Classification failed for %s: %s", email.id, exc)
        return ClassifiedNewsletter(
            email=email,
            is_newsletter=is_newsletter_heuristic,
            category="none",
            confidence=0.0,
            classification_reason=f"Classification error: {exc}",
        )

    is_newsletter = bool(result.get("is_newsletter", False)) or is_newsletter_heuristic
    confidence = float(result.get("confidence", 0.0))
    category = result.get("category", "none")

    if not is_newsletter or confidence < min_confidence:
        category = "none"

    return ClassifiedNewsletter(
        email=email,
        is_newsletter=is_newsletter,
        category=category,
        confidence=confidence,
        classification_reason=result.get("reason", ""),
    )


async def classify_emails(
    emails: list[RawEmail],
    filters: list[dict],
    llm: LLMClient,
    db: Database,
    min_confidence: float = 0.7,
) -> list[ClassifiedNewsletter]:
    results = []
    for email in emails:
        if await db.is_processed(email.id):
            continue
        classified = await classify_email(email, filters, llm, min_confidence)
        await db.mark_processed(
            email.id, classified.category, classified.is_newsletter
        )
        results.append(classified)
    return results
