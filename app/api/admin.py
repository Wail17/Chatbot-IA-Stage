"""Admin endpoints for managing the chatbot knowledge base.

Provides CRUD operations for Q&A entries, draft review workflow,
knowledge base management, and performance analytics.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import (
    DraftEditRequest,
    DraftStatsResponse,
    KnowledgeBaseCreate,
    KnowledgeBaseEntry,
    KnowledgeBaseUpdate,
    PerformanceStats,
    QADraftReview,
    QADraftSchema,
    WeeklyAnalytics,
)
from app.services.learning_engine import (
    approve_draft,
    delete_knowledge_entry,
    edit_draft,
    get_draft_stats,
    get_pending_drafts,
    get_weekly_analytics,
    reject_draft,
    update_knowledge_entry,
)
from app.services.vectorstore import get_knowledge_base_entries, get_performance_stats
from app.utils.logger import logger

router = APIRouter()


# ---------------------------------------------------------------------------
# Drafts Management
# ---------------------------------------------------------------------------


@router.get("/drafts", response_model=list[QADraftSchema])
async def list_drafts(
    status: str = Query("pending", description="Filter by status: pending, approved, rejected"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
) -> list[QADraftSchema]:
    """List Q&A draft suggestions for review.

    Args:
        status: Filter by review status.
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

    When approved:
    1. Generates embedding for the Q&A pair
    2. Adds to ChromaDB for semantic search
    3. Creates entry in qa_knowledge_base
    4. Marks draft as approved

    All steps are atomic — if vectorization fails, everything rolls back.

    Args:
        draft_id: The draft ID to review.
        review: The review action with optional corrections.

    Returns:
        Updated QADraftSchema.
    """
    logger.info("Admin reviewing draft %d - action=%s", draft_id, review.action)

    try:
        if review.action == "approve":
            result = await approve_draft(
                draft_id=draft_id,
                reviewer_note=review.reviewer_note,
                corrected_answer=review.corrected_answer,
                corrected_question=review.corrected_question,
            )
        else:
            result = await reject_draft(
                draft_id=draft_id,
                reviewer_note=review.reviewer_note,
            )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Vectorization failed: {exc}. Draft was NOT approved.",
        ) from exc
    except Exception as exc:
        logger.error("Error reviewing draft: %s", str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to review draft.") from exc


@router.put("/drafts/{draft_id}", response_model=QADraftSchema)
async def update_draft(draft_id: int, edit_request: DraftEditRequest) -> QADraftSchema:
    """Edit a Q&A draft without approving or rejecting it.

    Allows the client to refine the question/answer before making a decision.

    Args:
        draft_id: The draft ID to edit.
        edit_request: The edited question and/or answer.

    Returns:
        Updated QADraftSchema.
    """
    logger.info("Admin editing draft %d", draft_id)

    try:
        result = await edit_draft(
            draft_id=draft_id,
            edited_question=edit_request.edited_question,
            edited_answer=edit_request.edited_answer,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Error editing draft: %s", str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to edit draft.") from exc


@router.get("/drafts/stats", response_model=DraftStatsResponse)
async def draft_statistics() -> DraftStatsResponse:
    """Get statistics about Q&A drafts.

    Returns counts by status, by source, top categories, and
    number approved this week.

    Returns:
        DraftStatsResponse with aggregated statistics.
    """
    logger.info("Admin requesting draft stats")

    try:
        stats = await get_draft_stats()
        return DraftStatsResponse(**stats)
    except Exception as exc:
        logger.error("Error getting draft stats: %s", str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve draft stats.") from exc


# ---------------------------------------------------------------------------
# Knowledge Base Management
# ---------------------------------------------------------------------------


@router.get("/knowledge", response_model=list[KnowledgeBaseEntry])
async def list_knowledge_base(
    category: Optional[str] = Query(None, description="Filter by category"),
    language: Optional[str] = Query(None, description="Filter by language"),
    search: Optional[str] = Query(None, description="Search in questions/answers"),
    limit: int = Query(100, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> list[KnowledgeBaseEntry]:
    """List validated Q&A entries from the knowledge base.

    Args:
        category: Optional category filter.
        language: Optional language filter.
        search: Optional search term (not yet implemented in vectorstore).
        limit: Maximum number of results.
        offset: Pagination offset.

    Returns:
        List of KnowledgeBaseEntry objects.
    """
    logger.info(
        "Admin listing knowledge base - category=%s, lang=%s, search=%s",
        category,
        language,
        search,
    )

    try:
        entries = await get_knowledge_base_entries(
            category=category,
            language=language,
            limit=limit,
            offset=offset,
        )
        if search:
            search_lower = search.lower()
            entries = [
                e
                for e in entries
                if search_lower in e.question.lower() or search_lower in e.answer.lower()
            ]
        return entries
    except Exception as exc:
        logger.error("Error listing knowledge base: %s", str(exc), exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to retrieve knowledge base."
        ) from exc


@router.post("/knowledge", response_model=dict)
async def create_knowledge_entry(entry: KnowledgeBaseCreate) -> dict:
    """Manually add a new Q&A entry to the knowledge base.

    Generates an embedding and stores in both PostgreSQL and ChromaDB.

    Args:
        entry: The Q&A entry to create.

    Returns:
        Dictionary with the created entry ID.
    """
    logger.info("Admin creating knowledge entry - category=%s", entry.category)

    try:
        from sqlalchemy import insert

        from app.models.database import QAKnowledgeBase
        from app.services.embeddings import generate_embedding
        from app.services.vectorstore import add_to_vectorstore, get_async_session
        from app.utils.helpers import generate_chromadb_id

        chromadb_id = generate_chromadb_id(entry.category, entry.question)
        embedding_text = f"{entry.question} {entry.answer}"
        embedding = await generate_embedding(embedding_text)

        await add_to_vectorstore(
            doc_id=chromadb_id,
            text=entry.answer,
            embedding=embedding,
            metadata={
                "category": entry.category,
                "question": entry.question,
                "language": entry.language,
                "source": "manual",
            },
        )

        async with await get_async_session() as session:
            async with session.begin():
                result = await session.execute(
                    insert(QAKnowledgeBase)
                    .values(
                        category=entry.category,
                        question=entry.question,
                        answer=entry.answer,
                        language=entry.language,
                        source="manual",
                        chromadb_id=chromadb_id,
                        is_active=True,
                    )
                    .returning(QAKnowledgeBase.id)
                )
                qa_id = result.scalar_one()

        logger.info("Knowledge entry %d created manually", qa_id)
        return {"id": qa_id, "status": "created", "chromadb_id": chromadb_id}

    except Exception as exc:
        logger.error("Error creating knowledge entry: %s", str(exc), exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to create knowledge entry."
        ) from exc


@router.put("/knowledge/{qa_id}", response_model=dict)
async def update_qa(qa_id: int, body: KnowledgeBaseUpdate) -> dict:
    """Update an existing Q&A entry.

    Re-generates the embedding and updates ChromaDB.

    Args:
        qa_id: The knowledge base entry ID.
        body: Updated question and answer text.

    Returns:
        Dictionary with updated entry details.
    """
    logger.info("Admin updating knowledge entry %d", qa_id)

    try:
        result = await update_knowledge_entry(
            qa_id=qa_id,
            question=body.question,
            answer=body.answer,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Error updating knowledge entry: %s", str(exc), exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to update knowledge entry."
        ) from exc


@router.delete("/knowledge/{qa_id}", response_model=dict)
async def delete_qa(qa_id: int) -> dict:
    """Delete a Q&A entry from PostgreSQL and ChromaDB.

    Args:
        qa_id: The knowledge base entry ID.

    Returns:
        Dictionary confirming deletion.
    """
    logger.info("Admin deleting knowledge entry %d", qa_id)

    try:
        result = await delete_knowledge_entry(qa_id=qa_id)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Error deleting knowledge entry: %s", str(exc), exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to delete knowledge entry."
        ) from exc


# ---------------------------------------------------------------------------
# Analytics & Performance
# ---------------------------------------------------------------------------


@router.get("/analytics/weekly", response_model=list[WeeklyAnalytics])
async def get_weekly_analytics_endpoint(
    weeks: int = Query(12, ge=1, le=52, description="Number of weeks"),
) -> list[WeeklyAnalytics]:
    """Get weekly analytics data for the dashboard.

    Returns detailed weekly metrics including success rate,
    top unanswered questions, and knowledge base growth.

    Args:
        weeks: Number of recent weeks to include.

    Returns:
        List of WeeklyAnalytics objects.
    """
    logger.info("Admin requesting weekly analytics - weeks=%d", weeks)

    try:
        data = await get_weekly_analytics(weeks=weeks)
        return [WeeklyAnalytics(**w) for w in data]
    except Exception as exc:
        logger.error("Error getting weekly analytics: %s", str(exc), exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to retrieve analytics."
        ) from exc


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
        raise HTTPException(
            status_code=500, detail="Failed to retrieve performance data."
        ) from exc
