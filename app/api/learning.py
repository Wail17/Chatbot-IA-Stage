"""Learning system endpoints.

Provides endpoints for triggering and monitoring the
Human-in-the-Loop learning pipeline.
"""

from fastapi import APIRouter, HTTPException

from app.models.schemas import FeedbackResponse
from app.services.learning_engine import run_nightly_learning as run_learning_cycle, get_learning_stats
from app.utils.logger import logger

router = APIRouter()


@router.post("/trigger", response_model=FeedbackResponse)
async def trigger_learning() -> FeedbackResponse:
    """Manually trigger a learning cycle.

    Runs the pattern detection and draft generation pipeline
    on-demand instead of waiting for the nightly schedule.

    Returns:
        FeedbackResponse with learning cycle results summary.

    Raises:
        HTTPException: If the learning cycle fails.
    """
    logger.info("Manual learning cycle triggered")

    try:
        result = await run_learning_cycle()
        return FeedbackResponse(
            status="ok",
            message=f"Learning cycle completed. {result['drafts_created']} new drafts created.",
        )
    except Exception as exc:
        logger.error("Learning cycle error: %s", str(exc), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Learning cycle failed. Check logs for details.",
        ) from exc


@router.get("/stats")
async def learning_statistics() -> dict:
    """Get current learning system statistics.

    Returns metrics about the learning pipeline including
    pending signals, draft counts, and processing status.

    Returns:
        Dictionary with learning system statistics.

    Raises:
        HTTPException: If stats retrieval fails.
    """
    logger.info("Learning stats requested")

    try:
        stats = await get_learning_stats()
        return stats
    except Exception as exc:
        logger.error("Error getting learning stats: %s", str(exc), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve learning statistics.",
        ) from exc
