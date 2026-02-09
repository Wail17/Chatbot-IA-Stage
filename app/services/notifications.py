"""Notification service for admin alerts.

Handles email and webhook notifications for events like
new draft suggestions, low confidence alerts, and weekly reports.
"""

import httpx

from app.config import settings
from app.utils.logger import logger


async def notify_new_drafts(draft_count: int) -> None:
    """Notify admin about new Q&A draft suggestions.

    Args:
        draft_count: Number of new drafts created.
    """
    if draft_count == 0:
        return

    logger.info("Notification: %d new Q&A drafts ready for review", draft_count)


async def notify_low_confidence(
    question: str,
    confidence: float,
    session_id: str,
) -> None:
    """Notify admin about a low-confidence interaction.

    Triggered when the chatbot encounters a question it cannot
    answer confidently, indicating a potential knowledge gap.

    Args:
        question: The question that triggered the alert.
        confidence: The confidence score achieved.
        session_id: The session identifier.
    """
    logger.warning(
        "Low confidence alert (%.2f) - session=%s, question=%s...",
        confidence,
        session_id,
        question[:80],
    )


async def send_webhook(url: str, payload: dict) -> bool:
    """Send a webhook notification to an external URL.

    Args:
        url: The webhook endpoint URL.
        payload: The JSON payload to send.

    Returns:
        True if the webhook was sent successfully, False otherwise.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            logger.info("Webhook sent successfully to %s", url)
            return True
    except httpx.HTTPError as exc:
        logger.error("Webhook failed for %s: %s", url, str(exc))
        return False


async def send_weekly_report(stats: dict) -> None:
    """Send weekly performance report notification.

    Args:
        stats: Weekly performance statistics dictionary.
    """
    logger.info(
        "Weekly report - conversations=%d, avg_confidence=%.2f, "
        "thumbs_up=%d, thumbs_down=%d, new_qa=%d",
        stats.get("total_conversations", 0),
        stats.get("avg_confidence", 0.0),
        stats.get("thumbs_up_count", 0),
        stats.get("thumbs_down_count", 0),
        stats.get("new_qa_learned", 0),
    )
