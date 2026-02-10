"""Human-in-the-Loop learning engine.

Complete learning pipeline that:
1. Processes negative feedback and corrections from users
2. Detects recurring question patterns via semantic clustering
3. Generates master Q&A drafts using Claude Sonnet
4. Manages the nightly learning cycle
5. Handles draft approval/rejection with ChromaDB vectorization
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
from sqlalchemy import and_, delete, func, insert, select, update

from app.config import settings
from app.models.database import (
    Conversation,
    QADraft,
    QAKnowledgeBase,
    QAMismatchSignal,
    WeeklyPerformance,
)
from app.models.schemas import QADraftSchema
from app.services.embeddings import generate_embedding, generate_embeddings_batch
from app.services.vectorstore import (
    add_to_vectorstore,
    get_async_session,
    get_collection,
    search_similar,
)
from app.utils.helpers import generate_chromadb_id, now_utc
from app.utils.logger import logger


# ---------------------------------------------------------------------------
# 1. Feedback Processing
# ---------------------------------------------------------------------------


async def process_feedback(
    conversation_id: int,
    thumbs_up: bool,
    correction: str | None = None,
) -> dict[str, Any]:
    """Process user feedback on a conversation.

    For positive feedback, simply records the thumbs-up.
    For negative feedback or corrections, creates a mismatch signal and
    optionally a draft Q&A if a correction is provided.

    Args:
        conversation_id: The conversation to provide feedback on.
        thumbs_up: Whether the feedback is positive.
        correction: Optional corrected answer text.

    Returns:
        Dictionary with status and optional draft_id.

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

            if thumbs_up:
                logger.info("Positive feedback for conversation %d", conversation_id)
                return {"status": "recorded", "draft_id": None}

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

            draft_id = None
            if correction:
                result = await session.execute(
                    insert(QADraft)
                    .values(
                        question=conversation.question,
                        answer=correction,
                        category="User Correction",
                        language=conversation.language,
                        confidence=0.70,
                        source="user_correction",
                        pattern_count=1,
                        status="pending",
                    )
                    .returning(QADraft.id)
                )
                draft_id = result.scalar_one()
                logger.info(
                    "Draft %d created from user correction for conversation %d",
                    draft_id,
                    conversation_id,
                )

    return {"status": "recorded", "draft_id": draft_id}


# ---------------------------------------------------------------------------
# 2. Pattern Detection via Semantic Clustering
# ---------------------------------------------------------------------------


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        vec_a: First embedding vector.
        vec_b: Second embedding vector.

    Returns:
        Cosine similarity score between -1.0 and 1.0.
    """
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    dot = np.dot(a, b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    if norm == 0:
        return 0.0
    return float(dot / norm)


def _cluster_by_similarity(
    questions: list[str],
    embeddings: list[list[float]],
    threshold: float = 0.85,
) -> list[list[int]]:
    """Cluster question indices by cosine similarity.

    Uses a greedy approach: iterate through questions, assign each to the
    first cluster whose centroid is within the similarity threshold, or
    create a new cluster.

    Args:
        questions: List of question texts.
        embeddings: Corresponding embedding vectors.
        threshold: Minimum cosine similarity to join a cluster.

    Returns:
        List of clusters, each a list of question indices.
    """
    clusters: list[list[int]] = []
    centroids: list[list[float]] = []

    for idx, emb in enumerate(embeddings):
        placed = False
        for c_idx, centroid in enumerate(centroids):
            if _cosine_similarity(emb, centroid) >= threshold:
                clusters[c_idx].append(idx)
                placed = True
                break

        if not placed:
            clusters.append([idx])
            centroids.append(emb)

    return clusters


async def detect_recurring_patterns() -> list[dict[str, Any]]:
    """Detect recurring question patterns from low-confidence conversations.

    Queries conversations from the last 7 days with confidence below 0.5,
    clusters them by semantic similarity, and generates master Q&A drafts
    for clusters that meet the minimum size threshold.

    Returns:
        List of created drafts with their cluster sizes.
    """
    logger.info("Starting pattern detection")

    seven_days_ago = now_utc() - timedelta(days=7)

    async with await get_async_session() as session:
        result = await session.execute(
            select(Conversation.question, Conversation.language)
            .where(
                and_(
                    Conversation.confidence < 0.5,
                    Conversation.created_at >= seven_days_ago,
                    Conversation.thumbs_up.isnot(True),
                )
            )
            .order_by(Conversation.created_at.desc())
            .limit(500)
        )
        rows = result.all()

    if not rows:
        logger.info("No low-confidence conversations found for pattern detection")
        return []

    questions = [row.question for row in rows]
    languages = [row.language for row in rows]

    logger.info("Generating embeddings for %d low-confidence questions", len(questions))
    embeddings = await generate_embeddings_batch(questions)

    clusters = _cluster_by_similarity(questions, embeddings, threshold=0.85)

    min_size = settings.min_pattern_cluster_size
    significant_clusters = [c for c in clusters if len(c) >= min_size]

    logger.info(
        "Found %d clusters, %d meet min size %d",
        len(clusters),
        len(significant_clusters),
        min_size,
    )

    created_drafts: list[dict[str, Any]] = []

    for cluster_indices in significant_clusters:
        cluster_questions = [questions[i] for i in cluster_indices]
        cluster_language = languages[cluster_indices[0]]

        try:
            master_qa = await generate_master_qa(cluster_questions, cluster_language)
        except Exception as exc:
            logger.error("Failed to generate master Q&A: %s", str(exc))
            continue

        async with await get_async_session() as session:
            async with session.begin():
                result = await session.execute(
                    insert(QADraft)
                    .values(
                        question=master_qa["question"],
                        answer=master_qa["answer"],
                        category=master_qa.get("category", "General"),
                        language=cluster_language,
                        confidence=settings.auto_draft_threshold,
                        source="pattern_detection",
                        pattern_count=len(cluster_indices),
                        status="pending",
                    )
                    .returning(QADraft.id)
                )
                draft_id = result.scalar_one()

        created_drafts.append({
            "draft_id": draft_id,
            "question": master_qa["question"],
            "cluster_size": len(cluster_indices),
            "category": master_qa.get("category", "General"),
        })

        logger.info(
            "Pattern draft %d created from cluster of %d questions: %s",
            draft_id,
            len(cluster_indices),
            master_qa["question"][:60],
        )

    return created_drafts


# ---------------------------------------------------------------------------
# 3. Master Q&A Generation via Claude
# ---------------------------------------------------------------------------


async def generate_master_qa(
    question_cluster: list[str],
    language: str = "nl",
) -> dict[str, str]:
    """Use Claude Sonnet to synthesize a cluster of similar questions into one master Q&A.

    Takes multiple similar questions and generates a single canonical question
    with a comprehensive answer suitable for the FAQ knowledge base.

    Args:
        question_cluster: List of similar question texts.
        language: Target language code for the generated Q&A.

    Returns:
        Dictionary with 'question', 'answer', and 'category' keys.
    """
    from app.services.llm import _get_client

    language_names = {
        "nl": "Nederlands",
        "fr": "Français",
        "en": "English",
        "da": "Dansk",
    }
    lang_name = language_names.get(language, "Nederlands")

    questions_formatted = "\n".join(f"- {q}" for q in question_cluster[:20])

    prompt = f"""Je bent een FAQ-expert voor zwembad.eu (zwembaden en spa's).

Hieronder staan {len(question_cluster)} gelijkaardige klantvragen die het systeem niet goed kon beantwoorden:

{questions_formatted}

Genereer EEN uitgebreide FAQ entry die al deze vragen beantwoordt.

Antwoord ALLEEN in geldig JSON (geen markdown, geen uitleg):
{{
    "question": "De beste samengevatte vraag in {lang_name}",
    "answer": "Een uitgebreid, professioneel antwoord in {lang_name} (2-4 zinnen)",
    "category": "De beste categorie (kies uit: Onderhoud, Waterbehandeling, Prijzen, Installatie, Producten, Garantie, Levering, Technisch, Algemeen)"
}}"""

    client = _get_client()
    response = await client.messages.create(
        model=settings.claude_model_smart,
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = response.content[0].text.strip()

    start = response_text.find("{")
    end = response_text.rfind("}") + 1
    if start >= 0 and end > start:
        response_text = response_text[start:end]

    result = json.loads(response_text)

    required_keys = {"question", "answer", "category"}
    if not required_keys.issubset(result.keys()):
        raise ValueError(f"Missing keys in Claude response: {required_keys - result.keys()}")

    return result


# ---------------------------------------------------------------------------
# 4. Nightly Learning Cycle
# ---------------------------------------------------------------------------


async def run_nightly_learning() -> dict[str, Any]:
    """Execute the complete nightly learning cycle.

    Steps:
    1. Process all unprocessed mismatch signals (group + cluster)
    2. Detect recurring patterns from low-confidence conversations
    3. Generate weekly performance stats
    4. Notify admin if new drafts were created

    Returns:
        Dictionary with cycle statistics.
    """
    logger.info("=== Starting nightly learning cycle ===")

    signals_stats = await _process_unprocessed_signals()

    pattern_drafts = await detect_recurring_patterns()

    weekly_stats = await _generate_weekly_stats()

    total_drafts = signals_stats["drafts_created"] + len(pattern_drafts)

    if total_drafts > 0:
        from app.services.notifications import notify_new_drafts
        await notify_new_drafts(total_drafts)

    result = {
        "signals_processed": signals_stats["signals_processed"],
        "signal_drafts_created": signals_stats["drafts_created"],
        "pattern_drafts_created": len(pattern_drafts),
        "drafts_created": total_drafts,
        "weekly_stats": weekly_stats,
    }

    logger.info("=== Nightly learning cycle complete: %s ===", result)
    return result


async def _process_unprocessed_signals() -> dict[str, int]:
    """Process unprocessed mismatch signals by grouping and clustering.

    Groups signals by similar questions and creates drafts from clusters
    that have enough corrections.

    Returns:
        Dictionary with signals_processed and drafts_created counts.
    """
    async with await get_async_session() as session:
        async with session.begin():
            result = await session.execute(
                select(QAMismatchSignal)
                .where(QAMismatchSignal.processed.is_(False))
                .order_by(QAMismatchSignal.created_at)
            )
            signals = result.scalars().all()

            if not signals:
                return {"signals_processed": 0, "drafts_created": 0}

            logger.info("Processing %d unprocessed mismatch signals", len(signals))

            signal_questions = [s.original_question for s in signals]
            signal_embeddings = await generate_embeddings_batch(signal_questions)

            clusters = _cluster_by_similarity(
                signal_questions, signal_embeddings, threshold=0.85
            )

            drafts_created = 0
            min_size = settings.min_pattern_cluster_size

            for cluster_indices in clusters:
                if len(cluster_indices) < min_size:
                    continue

                cluster_signals = [signals[i] for i in cluster_indices]
                corrections = [
                    s.user_correction for s in cluster_signals if s.user_correction
                ]

                if corrections:
                    best_correction = max(corrections, key=len)
                    representative = cluster_signals[0]

                    await session.execute(
                        insert(QADraft).values(
                            question=representative.original_question,
                            answer=best_correction,
                            category="Learned",
                            language="nl",
                            confidence=settings.auto_draft_threshold,
                            source="signal_cluster",
                            pattern_count=len(cluster_indices),
                            status="pending",
                        )
                    )
                    drafts_created += 1

            signal_ids = [s.id for s in signals]
            await session.execute(
                update(QAMismatchSignal)
                .where(QAMismatchSignal.id.in_(signal_ids))
                .values(processed=True)
            )

    return {"signals_processed": len(signals), "drafts_created": drafts_created}


async def _generate_weekly_stats() -> dict[str, Any]:
    """Generate and store weekly performance statistics.

    Computes metrics for the current week and upserts them into
    the weekly_performance table.

    Returns:
        Dictionary with the computed weekly statistics.
    """
    now = now_utc()
    week_start = now - timedelta(days=now.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

    async with await get_async_session() as session:
        async with session.begin():
            convos = await session.execute(
                select(
                    func.count(Conversation.id).label("total"),
                    func.avg(Conversation.confidence).label("avg_conf"),
                    func.count(Conversation.id).filter(
                        Conversation.thumbs_up.is_(True)
                    ).label("thumbs_up"),
                    func.count(Conversation.id).filter(
                        Conversation.thumbs_up.is_(False)
                    ).label("thumbs_down"),
                ).where(Conversation.created_at >= week_start)
            )
            row = convos.one()

            new_qa = await session.execute(
                select(func.count(QAKnowledgeBase.id)).where(
                    and_(
                        QAKnowledgeBase.created_at >= week_start,
                        QAKnowledgeBase.source == "client_approved",
                    )
                )
            )
            new_qa_count = new_qa.scalar_one()

            low_conf = await session.execute(
                select(Conversation.question)
                .where(
                    and_(
                        Conversation.created_at >= week_start,
                        Conversation.confidence < 0.5,
                    )
                )
                .order_by(Conversation.created_at.desc())
                .limit(10)
            )
            top_unanswered = [r.question for r in low_conf.all()]

            stats = {
                "total_conversations": row.total or 0,
                "avg_confidence": round(float(row.avg_conf or 0), 4),
                "thumbs_up_count": row.thumbs_up or 0,
                "thumbs_down_count": row.thumbs_down or 0,
                "new_qa_learned": new_qa_count,
                "top_unanswered": top_unanswered,
            }

            week_number = now.isocalendar()[1]

            existing = await session.execute(
                select(WeeklyPerformance).where(
                    WeeklyPerformance.week_start == week_start
                )
            )
            if existing.scalar_one_or_none():
                await session.execute(
                    update(WeeklyPerformance)
                    .where(WeeklyPerformance.week_start == week_start)
                    .values(
                        week_number=week_number,
                        total_conversations=stats["total_conversations"],
                        avg_confidence=stats["avg_confidence"],
                        thumbs_up_count=stats["thumbs_up_count"],
                        thumbs_down_count=stats["thumbs_down_count"],
                        new_qa_learned=stats["new_qa_learned"],
                        top_unanswered=json.dumps(top_unanswered),
                    )
                )
            else:
                await session.execute(
                    insert(WeeklyPerformance).values(
                        week_start=week_start,
                        week_number=week_number,
                        total_conversations=stats["total_conversations"],
                        avg_confidence=stats["avg_confidence"],
                        thumbs_up_count=stats["thumbs_up_count"],
                        thumbs_down_count=stats["thumbs_down_count"],
                        new_qa_learned=stats["new_qa_learned"],
                        top_unanswered=json.dumps(top_unanswered),
                    )
                )

    return stats


# ---------------------------------------------------------------------------
# 5. Draft Management (approve / reject / edit)
# ---------------------------------------------------------------------------


async def get_pending_drafts(
    status: str = "pending",
    limit: int = 50,
) -> list[QADraftSchema]:
    """Retrieve Q&A drafts filtered by status.

    Args:
        status: Filter by review status (pending/approved/rejected).
        limit: Maximum results to return.

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
    corrected_question: str | None = None,
) -> QADraftSchema:
    """Approve a Q&A draft and add it to the knowledge base + ChromaDB.

    This is an atomic operation: if embedding or ChromaDB fails, the
    PostgreSQL transaction is rolled back.

    Args:
        draft_id: The draft to approve.
        reviewer_note: Optional review note.
        corrected_answer: Optional corrected answer to use instead.
        corrected_question: Optional corrected question to use instead.

    Returns:
        Updated QADraftSchema.

    Raises:
        ValueError: If the draft is not found.
        RuntimeError: If vectorization fails (triggers rollback).
    """
    async with await get_async_session() as session:
        async with session.begin():
            result = await session.execute(
                select(QADraft).where(QADraft.id == draft_id)
            )
            draft = result.scalar_one_or_none()

            if not draft:
                raise ValueError(f"Draft {draft_id} not found")

            final_question = corrected_question or draft.question
            final_answer = corrected_answer or draft.answer

            chromadb_id = generate_chromadb_id(draft.category, final_question)

            try:
                embedding_text = f"{final_question} {final_answer}"
                embedding = await generate_embedding(embedding_text)
                await add_to_vectorstore(
                    doc_id=chromadb_id,
                    text=final_answer,
                    embedding=embedding,
                    metadata={
                        "category": draft.category,
                        "question": final_question,
                        "language": draft.language,
                        "source": "client_approved",
                    },
                )
            except Exception as exc:
                logger.error("Vectorization failed for draft %d: %s", draft_id, str(exc))
                raise RuntimeError(
                    f"Failed to vectorize draft {draft_id}: {exc}"
                ) from exc

            await session.execute(
                insert(QAKnowledgeBase).values(
                    category=draft.category,
                    question=final_question,
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
                    reviewed_at=datetime.now(),  # Sans timezone!
                    reviewer_note=reviewer_note,
                    question=final_question,
                    answer=final_answer,
                )
            )

            result = await session.execute(
                select(QADraft).where(QADraft.id == draft_id)
            )
            updated_draft = result.scalar_one()

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
                    reviewed_at=datetime.now(timezone.utc),
                    reviewer_note=reviewer_note,
                )
            )

            result = await session.execute(
                select(QADraft).where(QADraft.id == draft_id)
            )
            updated_draft = result.scalar_one()

    logger.info("Draft %d rejected", draft_id)
    return QADraftSchema.model_validate(updated_draft)


async def edit_draft(
    draft_id: int,
    edited_question: str | None = None,
    edited_answer: str | None = None,
) -> QADraftSchema:
    """Edit a Q&A draft without changing its status.

    Args:
        draft_id: The draft to edit.
        edited_question: New question text.
        edited_answer: New answer text.

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

            update_values: dict[str, Any] = {}
            if edited_question is not None:
                update_values["question"] = edited_question
            if edited_answer is not None:
                update_values["answer"] = edited_answer

            if update_values:
                await session.execute(
                    update(QADraft)
                    .where(QADraft.id == draft_id)
                    .values(**update_values)
                )

            result = await session.execute(
                select(QADraft).where(QADraft.id == draft_id)
            )
            updated_draft = result.scalar_one()

    logger.info("Draft %d edited", draft_id)
    return QADraftSchema.model_validate(updated_draft)


# ---------------------------------------------------------------------------
# 6. Knowledge Base CRUD
# ---------------------------------------------------------------------------


async def update_knowledge_entry(
    qa_id: int,
    question: str,
    answer: str,
) -> dict[str, Any]:
    """Update an existing Q&A entry and re-vectorize in ChromaDB.

    Args:
        qa_id: The knowledge base entry ID.
        question: Updated question text.
        answer: Updated answer text.

    Returns:
        Dictionary with the updated entry details.

    Raises:
        ValueError: If the entry is not found.
    """
    async with await get_async_session() as session:
        async with session.begin():
            result = await session.execute(
                select(QAKnowledgeBase).where(QAKnowledgeBase.id == qa_id)
            )
            entry = result.scalar_one_or_none()

            if not entry:
                raise ValueError(f"Knowledge entry {qa_id} not found")

            old_chromadb_id = entry.chromadb_id
            new_chromadb_id = generate_chromadb_id(entry.category, question)

            embedding_text = f"{question} {answer}"
            embedding = await generate_embedding(embedding_text)

            if old_chromadb_id and old_chromadb_id != new_chromadb_id:
                try:
                    collection = get_collection()
                    collection.delete(ids=[old_chromadb_id])
                except Exception as exc:
                    logger.warning("Failed to delete old ChromaDB entry: %s", str(exc))

            await add_to_vectorstore(
                doc_id=new_chromadb_id,
                text=answer,
                embedding=embedding,
                metadata={
                    "category": entry.category,
                    "question": question,
                    "language": entry.language,
                    "source": entry.source,
                },
            )

            await session.execute(
                update(QAKnowledgeBase)
                .where(QAKnowledgeBase.id == qa_id)
                .values(
                    question=question,
                    answer=answer,
                    chromadb_id=new_chromadb_id,
                )
            )

    logger.info("Knowledge entry %d updated and re-vectorized", qa_id)
    return {"id": qa_id, "question": question, "answer": answer, "chromadb_id": new_chromadb_id}


async def delete_knowledge_entry(qa_id: int) -> dict[str, str]:
    """Delete a Q&A entry from PostgreSQL and ChromaDB.

    Args:
        qa_id: The knowledge base entry ID.

    Returns:
        Dictionary confirming deletion.

    Raises:
        ValueError: If the entry is not found.
    """
    async with await get_async_session() as session:
        async with session.begin():
            result = await session.execute(
                select(QAKnowledgeBase).where(QAKnowledgeBase.id == qa_id)
            )
            entry = result.scalar_one_or_none()

            if not entry:
                raise ValueError(f"Knowledge entry {qa_id} not found")

            if entry.chromadb_id:
                try:
                    collection = get_collection()
                    collection.delete(ids=[entry.chromadb_id])
                    logger.info("Removed %s from ChromaDB", entry.chromadb_id)
                except Exception as exc:
                    logger.warning("Failed to delete from ChromaDB: %s", str(exc))

            await session.execute(
                delete(QAKnowledgeBase).where(QAKnowledgeBase.id == qa_id)
            )

    logger.info("Knowledge entry %d deleted", qa_id)
    return {"status": "deleted", "id": str(qa_id)}


# ---------------------------------------------------------------------------
# 7. Analytics
# ---------------------------------------------------------------------------


async def get_learning_stats() -> dict[str, Any]:
    """Get comprehensive learning system statistics.

    Returns:
        Dictionary with signal counts, draft counts, knowledge base size,
        and pipeline configuration.
    """
    async with await get_async_session() as session:
        unprocessed_signals = await session.execute(
            select(func.count(QAMismatchSignal.id))
            .where(QAMismatchSignal.processed.is_(False))
        )

        total_signals = await session.execute(
            select(func.count(QAMismatchSignal.id))
        )

        pending_drafts = await session.execute(
            select(func.count(QADraft.id))
            .where(QADraft.status == "pending")
        )

        approved_drafts = await session.execute(
            select(func.count(QADraft.id))
            .where(QADraft.status == "approved")
        )

        rejected_drafts = await session.execute(
            select(func.count(QADraft.id))
            .where(QADraft.status == "rejected")
        )

        total_knowledge = await session.execute(
            select(func.count(QAKnowledgeBase.id))
            .where(QAKnowledgeBase.is_active.is_(True))
        )

        learned_knowledge = await session.execute(
            select(func.count(QAKnowledgeBase.id))
            .where(QAKnowledgeBase.source == "client_approved")
        )

        return {
            "unprocessed_signals": unprocessed_signals.scalar_one(),
            "total_signals": total_signals.scalar_one(),
            "pending_drafts": pending_drafts.scalar_one(),
            "approved_drafts": approved_drafts.scalar_one(),
            "rejected_drafts": rejected_drafts.scalar_one(),
            "total_knowledge_entries": total_knowledge.scalar_one(),
            "learned_entries": learned_knowledge.scalar_one(),
            "nightly_learning_enabled": settings.nightly_learning_enabled,
            "min_cluster_size": settings.min_pattern_cluster_size,
            "auto_draft_threshold": settings.auto_draft_threshold,
        }


async def get_weekly_analytics(weeks: int = 12) -> list[dict[str, Any]]:
    """Get weekly analytics for the dashboard trends.

    Args:
        weeks: Number of weeks to retrieve.

    Returns:
        List of weekly stats dictionaries ordered by week.
    """
    async with await get_async_session() as session:
        result = await session.execute(
            select(WeeklyPerformance)
            .order_by(WeeklyPerformance.week_start.desc())
            .limit(weeks)
        )
        rows = result.scalars().all()

        return [
            {
                "week_start": row.week_start.isoformat() if row.week_start else None,
                "week_number": row.week_number,
                "total_conversations": row.total_conversations,
                "avg_confidence": round(row.avg_confidence, 4),
                "thumbs_up_count": row.thumbs_up_count,
                "thumbs_down_count": row.thumbs_down_count,
                "escalation_count": row.escalation_count,
                "new_qa_learned": row.new_qa_learned,
                "success_rate": round(
                    row.thumbs_up_count / max(row.thumbs_up_count + row.thumbs_down_count, 1),
                    4,
                ),
                "top_unanswered": json.loads(row.top_unanswered)
                if row.top_unanswered
                else [],
            }
            for row in rows
        ]


async def get_draft_stats() -> dict[str, Any]:
    """Get draft-specific statistics.

    Returns:
        Dictionary with draft counts by status, sources, and top categories.
    """
    async with await get_async_session() as session:
        status_counts = await session.execute(
            select(QADraft.status, func.count(QADraft.id))
            .group_by(QADraft.status)
        )
        by_status = {row[0]: row[1] for row in status_counts.all()}

        source_counts = await session.execute(
            select(QADraft.source, func.count(QADraft.id))
            .group_by(QADraft.source)
        )
        by_source = {row[0]: row[1] for row in source_counts.all()}

        category_counts = await session.execute(
            select(QADraft.category, func.count(QADraft.id))
            .where(QADraft.status == "pending")
            .group_by(QADraft.category)
            .order_by(func.count(QADraft.id).desc())
            .limit(10)
        )
        top_categories = [
            {"category": row[0], "count": row[1]}
            for row in category_counts.all()
        ]

        seven_days_ago = now_utc() - timedelta(days=7)
        approved_this_week = await session.execute(
            select(func.count(QADraft.id)).where(
                and_(
                    QADraft.status == "approved",
                    QADraft.reviewed_at >= seven_days_ago,
                )
            )
        )

        return {
            "by_status": by_status,
            "by_source": by_source,
            "top_categories": top_categories,
            "approved_this_week": approved_this_week.scalar_one(),
        }
