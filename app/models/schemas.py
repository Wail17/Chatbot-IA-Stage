"""Pydantic request/response schemas for the API.

All API input validation and output serialization is handled through
these models using Pydantic v2.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Incoming chat message from a user.

    Attributes:
        question: The user's question text.
        language: Preferred language code (auto-detected if not provided).
        session_id: Unique session identifier for conversation grouping.
    """

    question: str = Field(..., min_length=1, max_length=2000, description="User question")
    language: Optional[str] = Field(
        None, max_length=5, description="Language code (nl, fr, en, da)"
    )
    session_id: Optional[str] = Field(
        None, max_length=64, description="Session ID for conversation tracking"
    )


class SourceReference(BaseModel):
    """A reference to the knowledge source used to generate an answer.

    Attributes:
        category: The knowledge base category.
        question: The matched FAQ question.
        similarity: Cosine similarity score.
    """

    category: str
    question: str
    similarity: float


class ChatResponse(BaseModel):
    """Chat response returned to the user.

    Attributes:
        answer: The generated answer text.
        confidence: Confidence score (0.0 - 1.0).
        sources: List of knowledge base sources used.
        used_model: Which Claude model generated the answer.
        language: Detected or requested language.
        conversation_id: Database ID for feedback reference.
        session_id: Session identifier.
    """

    answer: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    sources: list[SourceReference] = Field(default_factory=list)
    used_model: str
    language: str
    conversation_id: int
    session_id: str


class FeedbackRequest(BaseModel):
    """User feedback on a chat response.

    Attributes:
        conversation_id: ID of the conversation being rated.
        thumbs_up: True for positive, False for negative feedback.
        correction: Optional corrected answer text from the user.
    """

    conversation_id: int = Field(..., description="Conversation ID to provide feedback on")
    thumbs_up: bool = Field(..., description="Positive or negative feedback")
    correction: Optional[str] = Field(
        None, max_length=5000, description="Corrected answer if thumbs down"
    )


class FeedbackResponse(BaseModel):
    """Confirmation of feedback submission.

    Attributes:
        status: Processing status.
        message: Human-readable confirmation message.
    """

    status: str = "ok"
    message: str


class QADraftSchema(BaseModel):
    """A Q&A draft suggestion for admin review.

    Attributes:
        id: Draft ID.
        question: The suggested question.
        answer: The suggested answer.
        category: Suggested category.
        language: Language code.
        confidence: AI confidence in this suggestion.
        source: How this draft was generated.
        pattern_count: Number of similar questions detected.
        status: Review status (pending/approved/rejected).
        created_at: When this draft was created.
    """

    id: int
    question: str
    answer: str
    category: str
    language: str
    confidence: float
    source: str
    pattern_count: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class QADraftReview(BaseModel):
    """Admin review action on a Q&A draft.

    Attributes:
        action: Approve or reject the draft.
        reviewer_note: Optional note explaining the decision.
        corrected_answer: Optional corrected answer text.
    """

    action: str = Field(..., pattern="^(approve|reject)$", description="approve or reject")
    reviewer_note: Optional[str] = Field(None, max_length=1000)
    corrected_answer: Optional[str] = Field(None, max_length=5000)


class KnowledgeBaseEntry(BaseModel):
    """A validated Q&A entry in the knowledge base.

    Attributes:
        id: Entry ID.
        category: Topic category.
        question: The question.
        answer: The validated answer.
        language: Language code.
        source: Origin of this entry.
        is_active: Whether currently active.
        created_at: When created.
    """

    id: int
    category: str
    question: str
    answer: str
    language: str
    source: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class HealthResponse(BaseModel):
    """Health check response.

    Attributes:
        status: Service status.
        environment: Current environment.
        features: Active feature flags.
        version: Application version.
    """

    status: str = "healthy"
    environment: str
    features: dict[str, bool]
    version: str = "1.0.0"


class PerformanceStats(BaseModel):
    """Weekly performance statistics.

    Attributes:
        week_number: ISO week number.
        total_conversations: Total interactions.
        avg_confidence: Average confidence score.
        thumbs_up_count: Positive feedback count.
        thumbs_down_count: Negative feedback count.
        escalation_count: Escalation count.
        new_qa_learned: New Q&A pairs learned.
    """

    week_number: int
    total_conversations: int
    avg_confidence: float
    thumbs_up_count: int
    thumbs_down_count: int
    escalation_count: int
    new_qa_learned: int

    model_config = {"from_attributes": True}
