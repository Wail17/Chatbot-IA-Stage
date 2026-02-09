"""Admin endpoints for managing the chatbot knowledge base.

Provides CRUD operations for Q&A entries, draft review,
and performance analytics access.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import (
    KnowledgeBaseEntry,
    PerformanceStats,
    QADraftReview,
    QADraftSchema,
)
from app.services.learning_engine import approve_draft, get_pending_drafts, reject_draft
from app.services.vectorstore import get_knowledge_base_entries, get_performance_stats
from app.utils.logger import logger

router = APIRouter()


@router.get("/knowledge", response_model=list[KnowledgeBaseEntry])
async def list_knowledge_base(
    category: Optional[str] = Query(None, description="Filter by category"),
    language: Optional[str] = Query(None, description="Filter by language"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> list[KnowledgeBaseEntry]:
    """List validated Q&A entries from the knowledge base.

    Args:
        category: Optional category filter.
        language: Optional language filter.
        limit: Maximum number of results.
        offset: Pagination offset.

    Returns:
        List of KnowledgeBaseEntry objects.
    """
    logger.info("Admin listing knowledge base - category=%s, lang=%s", category, language)

    try:
        entries = await get_knowledge_base_entries(
            category=category,
            language=language,
            limit=limit,
            offset=offset,
        )
        return entries
    except Exception as exc:
        logger.error("Error listing knowledge base: %s", str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve knowledge base.") from exc


@router.get("/drafts", response_model=list[QADraftSchema])
async def list_drafts(
    status: str = Query("pending", description="Filter by status"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
) -> list[QADraftSchema]:
    """List Q&A draft suggestions for review.

    Args:
        status: Filter by review status (pending/approved/rejected).
        limit: Maximum number of results.

    Returns:
        List of QADraftSchema objects.
    """
    logger.info("Admin listing drafts - status=%s", status)

    try:
        drafts = await get_pending_drafts(status=status, limit=limit)
        return drafts
    except Exception as exc:
        logger.error("Error listing drafts: %s", str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve drafts.") from exc


@router.post("/drafts/{draft_id}/review", response_model=QADraftSchema)
async def review_draft(draft_id: int, review: QADraftReview) -> QADraftSchema:
    """Approve or reject a Q&A draft suggestion.

    When approved, the draft is moved to the knowledge base and
    vectorized in ChromaDB. When rejected, it is marked accordingly.

    Args:
        draft_id: The draft ID to review.
        review: The review action (approve/reject) with optional note.

    Returns:
        Updated QADraftSchema after review.

    Raises:
        HTTPException: If draft not found or review fails.
    """
    logger.info("Admin reviewing draft %d - action=%s", draft_id, review.action)

    try:
        if review.action == "approve":
            result = await approve_draft(
                draft_id=draft_id,
                reviewer_note=review.reviewer_note,
                corrected_answer=review.corrected_answer,
            )
        else:
            result = await reject_draft(
                draft_id=draft_id,
                reviewer_note=review.reviewer_note,
            )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Error reviewing draft: %s", str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to review draft.") from exc


@router.get("/performance", response_model=list[PerformanceStats])
async def get_performance(
    weeks: int = Query(4, ge=1, le=52, description="Number of weeks to retrieve"),
) -> list[PerformanceStats]:
    """Get weekly performance statistics.

    Args:
        weeks: Number of recent weeks to include.

    Returns:
        List of PerformanceStats for the requested period.
    """
    logger.info("Admin requesting performance stats - weeks=%d", weeks)

    try:
        stats = await get_performance_stats(weeks=weeks)
        return stats
    except Exception as exc:
        logger.error("Error getting performance: %s", str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve performance data.") from exc
