"""Semantic search and answer retrieval logic.

Orchestrates the full retrieval pipeline:
1. Embed the question
2. Search ChromaDB for similar Q&A pairs
3. Determine confidence level
4. Route to appropriate Claude model
5. Log the conversation
"""

from sqlalchemy import insert

from app.config import settings
from app.models.database import Conversation
from app.models.schemas import ChatResponse, SourceReference
from app.services.embeddings import generate_embedding
from app.services.llm import generate_answer_fast, generate_answer_smart
from app.services.vectorstore import get_async_session, search_similar
from app.utils.logger import logger


def _distance_to_confidence(distance: float) -> float:
    """Convert ChromaDB distance to a confidence score.

    ChromaDB returns L2 distance where lower = more similar.
    This converts to a 0-1 confidence scale.

    Args:
        distance: L2 distance from ChromaDB.

    Returns:
        Confidence score between 0.0 and 1.0.
    """
    confidence = max(0.0, 1.0 - (distance / 2.0))
    return round(confidence, 4)


def _build_context_from_results(results: list[dict]) -> str:
    """Build a context string from search results for the LLM.

    Args:
        results: List of search result dictionaries.

    Returns:
        Formatted context string.
    """
    context_parts = []
    for result in results:
        metadata = result.get("metadata", {})
        category = metadata.get("category", "General")
        question = metadata.get("question", "")
        answer = result.get("document", "")

        context_parts.append(
            f"[Category: {category}]\nQ: {question}\nA: {answer}"
        )

    return "\n\n---\n\n".join(context_parts)


async def retrieve_answer(
    question: str,
    language: str,
    session_id: str,
) -> ChatResponse:
    """Full retrieval pipeline: embed, search, generate, log.

    Routing strategy:
    - confidence >= 0.85: Use Haiku (fast) with matched context
    - confidence >= 0.60: Use Sonnet (smart) with matched context
    - confidence < 0.60: Use Sonnet (smart) without context (general knowledge)

    Args:
        question: The user's question.
        language: Detected or requested language.
        session_id: Conversation session identifier.

    Returns:
        ChatResponse with answer, confidence, sources, and metadata.
    """
    query_embedding = await generate_embedding(question)

    search_results = await search_similar(
        query_embedding=query_embedding,
        n_results=3,
        language_filter=language if settings.is_feature_enabled("multilingual") else None,
    )

    best_confidence = 0.0
    sources: list[SourceReference] = []

    if search_results:
        best_confidence = _distance_to_confidence(search_results[0]["distance"])

        for result in search_results:
            conf = _distance_to_confidence(result["distance"])
            if conf >= settings.confidence_threshold_smart:
                metadata = result.get("metadata", {})
                sources.append(SourceReference(
                    category=metadata.get("category", "General"),
                    question=metadata.get("question", ""),
                    similarity=conf,
                ))

    if best_confidence >= settings.confidence_threshold_direct:
        context = _build_context_from_results(search_results[:2])
        llm_result = await generate_answer_fast(question, language, context)
        source_type = "faq"
        logger.info("High confidence (%.2f) - using fast model", best_confidence)

    elif best_confidence >= settings.confidence_threshold_smart:
        context = _build_context_from_results(search_results[:3])
        llm_result = await generate_answer_smart(question, language, context)
        source_type = "faq"
        logger.info("Medium confidence (%.2f) - using smart model", best_confidence)

    else:
        llm_result = await generate_answer_smart(question, language)
        source_type = "generated"
        logger.info("Low confidence (%.2f) - using smart model without context", best_confidence)

    conversation_id = await _log_conversation(
        session_id=session_id,
        question=question,
        answer=llm_result["answer"],
        language=language,
        confidence=best_confidence,
        model_used=llm_result["model"],
        source_type=source_type,
    )

    return ChatResponse(
        answer=llm_result["answer"],
        confidence=best_confidence,
        sources=sources,
        used_model=llm_result["model"],
        language=language,
        conversation_id=conversation_id,
        session_id=session_id,
    )


async def _log_conversation(
    session_id: str,
    question: str,
    answer: str,
    language: str,
    confidence: float,
    model_used: str,
    source_type: str,
) -> int:
    """Log a conversation to PostgreSQL.

    Args:
        session_id: Session identifier.
        question: User's question.
        answer: Generated answer.
        language: Language code.
        confidence: Confidence score.
        model_used: Claude model used.
        source_type: Answer source type.

    Returns:
        The created conversation ID.
    """
    async with await get_async_session() as session:
        async with session.begin():
            result = await session.execute(
                insert(Conversation).values(
                    session_id=session_id,
                    question=question,
                    answer=answer,
                    language=language,
                    confidence=confidence,
                    model_used=model_used,
                    source_type=source_type,
                ).returning(Conversation.id)
            )
            conversation_id = result.scalar_one()

    logger.debug("Logged conversation %d", conversation_id)
    return conversation_id
