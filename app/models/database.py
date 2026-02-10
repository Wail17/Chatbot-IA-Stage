"""SQLAlchemy ORM models for the chatbot database.

Defines all database tables using SQLAlchemy 2.0 declarative style:
- conversations: Logs all chat interactions
- qa_knowledge_base: Validated Q&A pairs (source of truth)
- qa_drafts: AI-generated Q&A suggestions pending client validation
- qa_mismatch_signals: Negative feedback and correction tracking
- weekly_performance: Weekly analytics aggregation
- feature_flag_overrides: Manual feature flag overrides (dev dashboard)
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class Conversation(Base):
    """Logs every chat interaction for analytics and learning.

    Attributes:
        id: Primary key.
        session_id: Groups messages in a conversation session.
        question: User's original question.
        answer: Bot's response.
        language: Detected language code (nl, fr, en, da).
        confidence: Confidence score of the answer (0.0 - 1.0).
        model_used: Which Claude model was used (haiku/sonnet).
        source_type: Where the answer came from (faq, learned, generated).
        thumbs_up: User feedback (True=positive, False=negative, None=no feedback).
        created_at: Timestamp of the interaction.
    """

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(5), nullable=False, default="nl")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    model_used: Mapped[str] = mapped_column(String(50), nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="generated"
    )
    thumbs_up: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    correction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    mismatch_signals: Mapped[list["QAMismatchSignal"]] = relationship(
        back_populates="conversation"
    )


class QAKnowledgeBase(Base):
    """Validated Q&A pairs — the chatbot's source of truth.

    Entries here have been approved by the client and are used for
    direct answer retrieval. Each entry is also stored in ChromaDB
    for semantic search.

    Attributes:
        id: Primary key.
        category: Topic category (e.g., "Onderhoud", "Prijzen").
        question: The canonical question.
        answer: The validated answer.
        language: Language code of this Q&A pair.
        source: Origin of this entry (faq_import, client_approved, learned).
        chromadb_id: Corresponding vector ID in ChromaDB.
        is_active: Whether this entry is currently used for retrieval.
        created_at: When this entry was created.
        updated_at: When this entry was last modified.
    """

    __tablename__ = "qa_knowledge_base"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(5), nullable=False, default="nl")
    source: Mapped[str] = mapped_column(
        String(30), nullable=False, default="faq_import"
    )
    chromadb_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class QADraft(Base):
    """AI-generated Q&A suggestions pending client validation.

    The learning engine creates drafts from detected patterns in
    unanswered or poorly-answered questions. The client reviews
    and approves/rejects them via the admin interface.

    Attributes:
        id: Primary key.
        question: The suggested question pattern.
        answer: The AI-generated answer suggestion.
        category: Suggested category.
        language: Language code.
        confidence: How confident the AI is in this suggestion (0.0 - 1.0).
        source: How this draft was created (pattern_cluster, mismatch_analysis).
        pattern_count: Number of similar questions that triggered this draft.
        status: Review status (pending, approved, rejected).
        reviewed_at: When the client reviewed this draft.
        reviewer_note: Optional note from the reviewer.
        created_at: When this draft was generated.
    """

    __tablename__ = "qa_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="General")
    language: Mapped[str] = mapped_column(String(5), nullable=False, default="nl")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pattern_cluster"
    )
    pattern_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reviewer_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class QAMismatchSignal(Base):
    """Tracks negative feedback and corrections from users.

    When a user gives thumbs-down or provides a correction, this is
    recorded as a mismatch signal. The learning engine aggregates
    these signals to identify knowledge gaps.

    Attributes:
        id: Primary key.
        conversation_id: Reference to the original conversation.
        original_question: The question that received poor response.
        original_answer: The answer that was deemed incorrect.
        user_correction: The correction provided by the user (if any).
        signal_type: Type of signal (thumbs_down, correction, escalation).
        processed: Whether the learning engine has processed this signal.
        created_at: When this signal was recorded.
    """

    __tablename__ = "qa_mismatch_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("conversations.id"), nullable=False, index=True
    )
    original_question: Mapped[str] = mapped_column(Text, nullable=False)
    original_answer: Mapped[str] = mapped_column(Text, nullable=False)
    user_correction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    signal_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="thumbs_down"
    )
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    conversation: Mapped["Conversation"] = relationship(
        back_populates="mismatch_signals"
    )


class WeeklyPerformance(Base):
    """Weekly analytics aggregation for performance tracking.

    Stores pre-computed metrics per week for the dashboard. Generated
    by a scheduled job every Monday.

    Attributes:
        id: Primary key.
        week_start: Start date of the reporting week.
        week_number: ISO week number.
        total_conversations: Total chat interactions that week.
        avg_confidence: Average confidence score across all answers.
        thumbs_up_count: Number of positive feedback signals.
        thumbs_down_count: Number of negative feedback signals.
        escalation_count: Number of escalations to human support.
        new_qa_learned: Number of new Q&A pairs added via learning.
        top_unanswered: JSON string of top unanswered questions.
        created_at: When this report was generated.
    """

    __tablename__ = "weekly_performance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    week_start: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    total_conversations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    thumbs_up_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    thumbs_down_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    escalation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_qa_learned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    top_unanswered: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class FeatureFlagOverride(Base):
    """Manual feature flag overrides for the developer dashboard.

    Allows developers to enable/disable features independently of the
    date-based activation schedule. Overrides take priority over
    date-based and env-var-based settings.

    Attributes:
        id: Primary key.
        feature_name: Name of the feature (multilingual, b2b, etc.).
        enabled: Whether the feature is force-enabled or force-disabled.
        override_by: Name of the developer who set the override.
        override_at: When the override was last changed.
        notes: Reason for the override.
    """

    __tablename__ = "feature_flag_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feature_name: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    override_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    override_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
