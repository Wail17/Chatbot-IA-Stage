"""Human-in-the-Loop learning engine.

Processes feedback signals, detects question patterns,
generates Q&A draft suggestions, and manages the learning lifecycle.
"""

from datetime import datetime

from sqlalchemy import func, select, update, insert

from app.config import settings
from app.models.database import (
    Conversation,
    QADraft,
    QAKnowledgeBase,
    QAMismatchSignal,
)
from app.models.schemas import QADraftSchema
from app.services.embeddings import generate_embedding
from app.services.vectorstore import add_to_vectorstore, get_async_session
from app.utils.helpers import generate_chromadb_id
from app.utils.logger import logger


async def process_feedback(
    conversation_id: int,
    thumbs_up: bool,
    correction: str | None = None,
) -> None:
    """Process user feedback on a conversation.

    For negative feedback or corrections, creates a mismatch signal
    that feeds into the learning pipeline.

    Args:
        conversation_id: The conversation to provide feedback on.
        thumbs_up: Whether the feedback is positive.
        correction: Optional corrected answer text.

    Raises:
        ValueError: If the conversation_id does not exist.
    """
    async with await get_async_session() as session:
        async with session.begin():
            result = await session.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )
            conversation = result.scalar_one_or_none()

            if not conversation:
                raise ValueError(f"Conversation {conversation_id} not found")

            await session.execute(
                update(Conversation)
                .where(Conversation.id == conversation_id)
                .values(thumbs_up=thumbs_up, correction=correction)
            )

            if not thumbs_up:
                signal_type = "correction" if correction else "thumbs_down"
                await session.execute(
                    insert(QAMismatchSignal).values(
                        conversation_id=conversation_id,
                        original_question=conversation.question,
                        original_answer=conversation.answer,
                        user_correction=correction,
                        signal_type=signal_type,
                    )
                )
                logger.info(
                    "Mismatch signal created for conversation %d (type=%s)",
                    conversation_id,
                    signal_type,
                )


async def run_learning_cycle() -> dict:
    """Execute a full learning cycle.

    Steps:
    1. Gather unprocessed mismatch signals
    2. Cluster similar questions
    3. Generate draft Q&A suggestions for frequent patterns
    4. Mark signals as processed

    Returns:
        Dictionary with learning cycle statistics.
    """
    logger.info("Starting learning cycle")

    async with await get_async_session() as session:
        async with session.begin():
            result = await session.execute(
                select(QAMismatchSignal)
                .where(QAMismatchSignal.processed.is_(False))
                .order_by(QAMismatchSignal.created_at)
            )
            signals = result.scalars().all()

            if not signals:
                logger.info("No unprocessed signals found")
                return {"drafts_created": 0, "signals_processed": 0}

            logger.info("Processing %d unprocessed signals", len(signals))

            question_groups: dict[str, list[QAMismatchSignal]] = {}
            for signal in signals:
                key = signal.original_question.lower().strip()[:100]
                if key not in question_groups:
                    question_groups[key] = []
                question_groups[key].append(signal)

            drafts_created = 0
            for question_key, group in question_groups.items():
                if len(group) >= settings.min_pattern_cluster_size:
                    corrections = [
                        s.user_correction for s in group if s.user_correction
                    ]

                    if corrections:
                        best_correction = max(corrections, key=len)
                        representative_question = group[0].original_question

                        await session.execute(
                            insert(QADraft).values(
                                question=representative_question,
                                answer=best_correction,
                                category="Learned",
                                confidence=settings.auto_draft_threshold,
                                source="pattern_cluster",
                                pattern_count=len(group),
                                status="pending",
                            )
                        )
                        drafts_created += 1

                        logger.info(
                            "Draft created from %d signals: %s...",
                            len(group),
                            representative_question[:60],
                        )

            signal_ids = [s.id for s in signals]
            await session.execute(
                update(QAMismatchSignal)
                .where(QAMismatchSignal.id.in_(signal_ids))
                .values(processed=True)
            )

    logger.info(
        "Learning cycle complete: %d drafts created, %d signals processed",
        drafts_created,
        len(signals),
    )

    return {"drafts_created": drafts_created, "signals_processed": len(signals)}


async def get_pending_drafts(
    status: str = "pending",
    limit: int = 50,
) -> list[QADraftSchema]:
    """Retrieve Q&A drafts filtered by status.

    Args:
        status: Filter by review status.
        limit: Maximum results.

    Returns:
        List of QADraftSchema objects.
    """
    async with await get_async_session() as session:
        result = await session.execute(
            select(QADraft)
            .where(QADraft.status == status)
            .order_by(QADraft.created_at.desc())
            .limit(limit)
        )
        drafts = result.scalars().all()
        return [QADraftSchema.model_validate(d) for d in drafts]


async def approve_draft(
    draft_id: int,
    reviewer_note: str | None = None,
    corrected_answer: str | None = None,
) -> QADraftSchema:
    """Approve a Q&A draft and add it to the knowledge base.

    Creates a new entry in qa_knowledge_base and vectorizes it
    in ChromaDB for immediate availability.

    Args:
        draft_id: The draft to approve.
        reviewer_note: Optional review note.
        corrected_answer: Optional corrected answer to use instead.

    Returns:
        Updated QADraftSchema.

    Raises:
        ValueError: If the draft is not found.
    """
    async with await get_async_session() as session:
        async with session.begin():
            result = await session.execute(
                select(QADraft).where(QADraft.id == draft_id)
            )
            draft = result.scalar_one_or_none()

            if not draft:
                raise ValueError(f"Draft {draft_id} not found")

            final_answer = corrected_answer or draft.answer

            chromadb_id = generate_chromadb_id(draft.category, draft.question)

            await session.execute(
                insert(QAKnowledgeBase).values(
                    category=draft.category,
                    question=draft.question,
                    answer=final_answer,
                    language=draft.language,
                    source="client_approved",
                    chromadb_id=chromadb_id,
                    is_active=True,
                )
            )

            await session.execute(
                update(QADraft)
                .where(QADraft.id == draft_id)
                .values(
                    status="approved",
                    reviewed_at=datetime.utcnow(),
                    reviewer_note=reviewer_note,
                    answer=final_answer,
                )
            )

            result = await session.execute(
                select(QADraft).where(QADraft.id == draft_id)
            )
            updated_draft = result.scalar_one()

    embedding_text = f"{updated_draft.question} {final_answer}"
    embedding = await generate_embedding(embedding_text)
    await add_to_vectorstore(
        doc_id=chromadb_id,
        text=final_answer,
        embedding=embedding,
        metadata={
            "category": updated_draft.category,
            "question": updated_draft.question,
            "language": updated_draft.language,
            "source": "client_approved",
        },
    )

    logger.info("Draft %d approved and added to knowledge base", draft_id)
    return QADraftSchema.model_validate(updated_draft)


async def reject_draft(
    draft_id: int,
    reviewer_note: str | None = None,
) -> QADraftSchema:
    """Reject a Q&A draft.

    Args:
        draft_id: The draft to reject.
        reviewer_note: Optional reason for rejection.

    Returns:
        Updated QADraftSchema.

    Raises:
        ValueError: If the draft is not found.
    """
    async with await get_async_session() as session:
        async with session.begin():
            result = await session.execute(
                select(QADraft).where(QADraft.id == draft_id)
            )
            draft = result.scalar_one_or_none()

            if not draft:
                raise ValueError(f"Draft {draft_id} not found")

            await session.execute(
                update(QADraft)
                .where(QADraft.id == draft_id)
                .values(
                    status="rejected",
                    reviewed_at=datetime.utcnow(),
                    reviewer_note=reviewer_note,
                )
            )

            result = await session.execute(
                select(QADraft).where(QADraft.id == draft_id)
            )
            updated_draft = result.scalar_one()

    logger.info("Draft %d rejected", draft_id)
    return QADraftSchema.model_validate(updated_draft)


async def get_learning_stats() -> dict:
    """Get learning system statistics.

    Returns:
        Dictionary with signal counts, draft counts, and pipeline status.
    """
    async with await get_async_session() as session:
        unprocessed_signals = await session.execute(
            select(func.count(QAMismatchSignal.id))
            .where(QAMismatchSignal.processed.is_(False))
        )

        pending_drafts = await session.execute(
            select(func.count(QADraft.id))
            .where(QADraft.status == "pending")
        )

        approved_drafts = await session.execute(
            select(func.count(QADraft.id))
            .where(QADraft.status == "approved")
        )

        total_knowledge = await session.execute(
            select(func.count(QAKnowledgeBase.id))
            .where(QAKnowledgeBase.is_active.is_(True))
        )

        return {
            "unprocessed_signals": unprocessed_signals.scalar_one(),
            "pending_drafts": pending_drafts.scalar_one(),
            "approved_drafts": approved_drafts.scalar_one(),
            "total_knowledge_entries": total_knowledge.scalar_one(),
            "nightly_learning_enabled": settings.nightly_learning_enabled,
            "min_cluster_size": settings.min_pattern_cluster_size,
            "auto_draft_threshold": settings.auto_draft_threshold,
        }
