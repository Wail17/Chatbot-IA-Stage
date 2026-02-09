"""Pydantic request/response schemas for the API.

All API input validation and output serialization is handled through
these models using Pydantic v2.
"""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """Incoming chat message from a user."""

    question: str = Field(..., min_length=1, max_length=2000, description="User question")
    language: Optional[str] = Field(
        None, max_length=5, description="Language code (nl, fr, en, da)"
    )
    session_id: Optional[str] = Field(
        None, max_length=64, description="Session ID for conversation tracking"
    )


class SourceReference(BaseModel):
    """A reference to the knowledge source used to generate an answer."""

    category: str
    question: str
    similarity: float


class ChatResponse(BaseModel):
    """Chat response returned to the user."""

    answer: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    sources: list[SourceReference] = Field(default_factory=list)
    used_model: str
    language: str
    conversation_id: int
    session_id: str


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------


class FeedbackRequest(BaseModel):
    """User feedback on a chat response."""

    conversation_id: int = Field(..., description="Conversation ID to provide feedback on")
    thumbs_up: bool = Field(..., description="Positive or negative feedback")
    correction: Optional[str] = Field(
        None, max_length=5000, description="Corrected answer if thumbs down"
    )


class FeedbackResponse(BaseModel):
    """Confirmation of feedback submission."""

    status: str = "ok"
    message: str
    draft_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Drafts
# ---------------------------------------------------------------------------


class QADraftSchema(BaseModel):
    """A Q&A draft suggestion for admin review."""

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
    """Admin review action on a Q&A draft (approve/reject)."""

    action: str = Field(
        ..., pattern="^(approve|reject)$", description="approve or reject"
    )
    reviewer_note: Optional[str] = Field(None, max_length=1000)
    corrected_answer: Optional[str] = Field(None, max_length=5000)
    corrected_question: Optional[str] = Field(None, max_length=2000)


class DraftEditRequest(BaseModel):
    """Edit request for a Q&A draft without approving/rejecting."""

    edited_question: Optional[str] = Field(None, max_length=2000)
    edited_answer: Optional[str] = Field(None, max_length=5000)


class DraftStatsResponse(BaseModel):
    """Statistics about Q&A drafts."""

    by_status: dict[str, int]
    by_source: dict[str, int]
    top_categories: list[dict[str, int | str]]
    approved_this_week: int


# ---------------------------------------------------------------------------
# Knowledge Base
# ---------------------------------------------------------------------------


class KnowledgeBaseEntry(BaseModel):
    """A validated Q&A entry in the knowledge base."""

    id: int
    category: str
    question: str
    answer: str
    language: str
    source: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeBaseUpdate(BaseModel):
    """Request to update an existing Q&A entry."""

    question: str = Field(..., min_length=1, max_length=2000)
    answer: str = Field(..., min_length=1, max_length=5000)


class KnowledgeBaseCreate(BaseModel):
    """Request to create a new Q&A entry."""

    question: str = Field(..., min_length=1, max_length=2000)
    answer: str = Field(..., min_length=1, max_length=5000)
    category: str = Field(..., min_length=1, max_length=100)
    language: str = Field(default="nl", max_length=5)


# ---------------------------------------------------------------------------
# Health & Analytics
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    environment: str
    features: dict[str, bool]
    version: str = "1.0.0"


class PerformanceStats(BaseModel):
    """Weekly performance statistics."""

    week_number: int
    total_conversations: int
    avg_confidence: float
    thumbs_up_count: int
    thumbs_down_count: int
    escalation_count: int
    new_qa_learned: int

    model_config = {"from_attributes": True}


class WeeklyAnalytics(BaseModel):
    """Detailed weekly analytics for the dashboard."""

    week_start: Optional[str] = None
    week_number: int
    total_conversations: int
    avg_confidence: float
    thumbs_up_count: int
    thumbs_down_count: int
    escalation_count: int
    new_qa_learned: int
    success_rate: float
    top_unanswered: list[str] = Field(default_factory=list)
