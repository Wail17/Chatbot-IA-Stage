"""Chat endpoint for the chatbot API.

Handles incoming chat messages, performs semantic search,
generates answers using Claude, and logs conversations.
"""

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.models.schemas import ChatRequest, ChatResponse, FeedbackRequest, FeedbackResponse
from app.services.retrieval import retrieve_answer
from app.utils.helpers import detect_language, generate_session_id
from app.utils.logger import logger

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Process a chat message and return an AI-generated answer.

    Flow:
    1. Detect language (if not provided)
    2. Search knowledge base via ChromaDB semantic search
    3. If high confidence match: respond with Haiku (fast)
    4. If medium confidence: respond with Sonnet (smart)
    5. If low confidence: generate best-effort answer + flag for review
    6. Log conversation to database

    Args:
        request: ChatRequest with question, optional language, optional session_id.

    Returns:
        ChatResponse with answer, confidence, sources, and metadata.

    Raises:
        HTTPException: If an internal error occurs during processing.
    """
    session_id = request.session_id or generate_session_id()
    language = request.language or detect_language(request.question)

    if settings.is_feature_enabled("multilingual"):
        supported = settings.get_supported_languages_list()
        if language not in supported:
            language = settings.default_language
    else:
        language = settings.default_language

    logger.info(
        "Chat request - session=%s, lang=%s, question=%s...",
        session_id,
        language,
        request.question[:80],
    )

    try:
        response = await retrieve_answer(
            question=request.question,
            language=language,
            session_id=session_id,
        )
        return response

    except Exception as exc:
        logger.error("Chat processing error: %s", str(exc), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing your question. Please try again.",
        ) from exc


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(request: FeedbackRequest) -> FeedbackResponse:
    """Submit feedback on a chat response.

    Records thumbs up/down and optional corrections. Corrections
    feed into the Human-in-the-Loop learning pipeline.

    Args:
        request: FeedbackRequest with conversation_id, rating, and optional correction.

    Returns:
        FeedbackResponse confirming feedback was recorded.

    Raises:
        HTTPException: If the conversation_id is not found.
    """
    from app.services.learning_engine import process_feedback

    logger.info(
        "Feedback received - conversation_id=%d, thumbs_up=%s, has_correction=%s",
        request.conversation_id,
        request.thumbs_up,
        request.correction is not None,
    )

    try:
        result = await process_feedback(
            conversation_id=request.conversation_id,
            thumbs_up=request.thumbs_up,
            correction=request.correction,
        )

        message = "Thank you for your feedback!"
        if request.correction:
            message = "Thank you! Your correction will be reviewed by our team."

        return FeedbackResponse(
            status="ok",
            message=message,
            draft_id=result.get("draft_id"),
        )

    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Feedback processing error: %s", str(exc), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing your feedback.",
        ) from exc
