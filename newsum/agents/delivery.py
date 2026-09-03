import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from core.models import DailySummary

logger = logging.getLogger(__name__)


ACRONYMS = {"ai", "api", "ipo", "gpu", "llm"}


def _category_display(category: str) -> str:
    words = category.replace("_", " ").split(" ")
    return " ".join(w.upper() if w.lower() in ACRONYMS else w.capitalize() for w in words)


def format_markdown(summary: DailySummary) -> str:
    lines = [
        f"# {_category_display(summary.category)} Newsletter Brief — {summary.date}",
        "",
        f"> {summary.newsletters_processed} newsletters processed "
        f"· Generated at {summary.generated_at.strftime('%H:%M UTC')}",
        "",
        "---",
        "",
        "## Top 10 Topics" if len(summary.points) == 10 else "## Top Topics",
        "",
    ]
    for point in summary.points:
        lines.append(f"**{point.rank}. {point.headline}**")
        lines.append("")
        lines.append(point.detail)
        lines.append("")
        lines.append(f"*Sources: {', '.join(point.sources)}*")
        lines.append("")
    return "\n".join(lines)


def write_markdown(summary: DailySummary, output_dir: str = "outputs/") -> Path:
    """Layer 5, Output 1: Always write the category brief to disk."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    file_path = out_path / f"{summary.date}_{summary.category}.md"
    file_path.write_text(format_markdown(summary))
    logger.info("Wrote %s", file_path)
    return file_path


def write_digest(
    summaries: list[DailySummary], date: str, output_dir: str = "outputs/"
) -> Path:
    """Layer 5, Output 2: Concatenate all category summaries with a table of contents."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    file_path = out_path / f"{date}_digest.md"

    toc = ["# Daily Newsletter Digest — " + date, "", "## Contents", ""]
    body = []
    for summary in summaries:
        display = _category_display(summary.category)
        anchor = display.lower().replace(" ", "-")
        toc.append(f"- [{display}](#{anchor})")
        body.append(format_markdown(summary))
        body.append("\n---\n")

    file_path.write_text("\n".join(toc) + "\n\n" + "\n".join(body))
    logger.info("Wrote %s", file_path)
    return file_path


def send_email_digest(digest_path: Path) -> None:
    """Layer 5, Output 3 (optional): Email the digest to self via Gmail SMTP."""
    if os.getenv("SEND_EMAIL_DIGEST", "false").lower() != "true":
        return

    self_email = os.getenv("SELF_EMAIL")
    app_password = os.getenv("SMTP_APP_PASSWORD")
    if not self_email or not app_password:
        logger.warning("SEND_EMAIL_DIGEST is true but SELF_EMAIL/SMTP_APP_PASSWORD unset")
        return

    body = digest_path.read_text()
    msg = MIMEMultipart()
    msg["From"] = self_email
    msg["To"] = self_email
    msg["Subject"] = f"Newsletter Digest — {digest_path.stem}"
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(self_email, app_password)
            server.send_message(msg)
        logger.info("Emailed digest to %s", self_email)
    except smtplib.SMTPException as exc:
        logger.error("Failed to email digest: %s", exc)


def deliver(summaries: list[DailySummary], date: str, output_dir: str = "outputs/") -> None:
    for summary in summaries:
        write_markdown(summary, output_dir)
    if summaries:
        digest_path = write_digest(summaries, date, output_dir)
        send_email_digest(digest_path)
