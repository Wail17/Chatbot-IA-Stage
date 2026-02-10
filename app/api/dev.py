"""Developer dashboard API endpoints.

Provides feature flag management, system health checks, and
real-time monitoring. Protected by a simple password header.
"""

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.config import settings
from app.models.database import Conversation, QADraft, QAKnowledgeBase, QAMismatchSignal
from app.services.feature_flags import (
    get_all_feature_status,
    remove_feature_override,
    set_feature_override,
)
from app.services.vectorstore import get_async_session, get_collection
from app.utils.logger import logger

router = APIRouter()


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------


async def verify_dev_password(
    x_dev_password: str = Header(..., description="Developer password"),
) -> None:
    """Verify the developer password from the request header.

    Args:
        x_dev_password: Password sent in the X-Dev-Password header.

    Raises:
        HTTPException: If the password is missing or incorrect.
    """
    if x_dev_password != settings.dev_password:
        raise HTTPException(status_code=401, detail="Invalid developer password")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class FeatureToggleRequest(BaseModel):
    """Request to toggle a feature flag."""

    enabled: bool = Field(..., description="Enable or disable the feature")
    override_by: str = Field(..., min_length=1, max_length=100, description="Developer name")
    notes: str = Field(default="", max_length=500, description="Reason for override")


# ---------------------------------------------------------------------------
# Feature Flags
# ---------------------------------------------------------------------------


@router.get("/features")
async def get_features(
    _: None = Depends(verify_dev_password),
) -> dict[str, dict[str, Any]]:
    """Get status of all feature flags with their source.

    Returns:
        Dictionary with each feature's status, source, and metadata.
    """
    logger.info("Dev dashboard: feature flags requested")
    return await get_all_feature_status()


@router.post("/features/{feature_name}/toggle")
async def toggle_feature(
    feature_name: str,
    request: FeatureToggleRequest,
    _: None = Depends(verify_dev_password),
) -> dict[str, Any]:
    """Manually enable or disable a feature flag.

    Creates a database override that takes priority over date-based activation.

    Args:
        feature_name: Feature to toggle (multilingual, b2b, calculator, youtube, crm).
        request: Toggle details with enabled state and reason.

    Returns:
        Confirmation with the new feature state.
    """
    logger.info(
        "Dev dashboard: toggling %s to %s by %s",
        feature_name,
        request.enabled,
        request.override_by,
    )

    try:
        result = await set_feature_override(
            feature_name=feature_name,
            enabled=request.enabled,
            override_by=request.override_by,
            notes=request.notes,
        )
        return {"status": "ok", **result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/features/{feature_name}/override")
async def remove_override(
    feature_name: str,
    _: None = Depends(verify_dev_password),
) -> dict[str, str]:
    """Remove a manual override, reverting to date-based activation.

    Args:
        feature_name: Feature to revert.

    Returns:
        Confirmation of override removal.
    """
    logger.info("Dev dashboard: removing override for %s", feature_name)
    return await remove_feature_override(feature_name)


# ---------------------------------------------------------------------------
# System Health
# ---------------------------------------------------------------------------


@router.get("/system/health")
async def system_health(
    _: None = Depends(verify_dev_password),
) -> dict[str, Any]:
    """Comprehensive system health check.

    Tests connectivity to PostgreSQL, ChromaDB, and reports API key status.

    Returns:
        Dictionary with health status for each component.
    """
    logger.info("Dev dashboard: health check requested")

    health: dict[str, Any] = {
        "status": "healthy",
        "environment": settings.environment,
        "components": {},
    }

    # PostgreSQL
    try:
        async with await get_async_session() as session:
            await session.execute(select(func.count(Conversation.id)))
        health["components"]["postgresql"] = {"status": "connected"}
    except Exception as exc:
        health["components"]["postgresql"] = {"status": "error", "detail": str(exc)}
        health["status"] = "degraded"

    # ChromaDB
    try:
        collection = get_collection()
        count = collection.count()
        health["components"]["chromadb"] = {
            "status": "connected",
            "documents": count,
        }
    except Exception as exc:
        health["components"]["chromadb"] = {"status": "error", "detail": str(exc)}
        health["status"] = "degraded"

    # API Keys
    health["components"]["anthropic_api"] = {
        "status": "configured" if settings.anthropic_api_key else "missing",
    }
    health["components"]["openai_api"] = {
        "status": "configured" if settings.openai_api_key else "missing",
    }

    # Feature flags
    health["features"] = await get_all_feature_status()

    return health


# ---------------------------------------------------------------------------
# System Stats
# ---------------------------------------------------------------------------


@router.get("/system/stats")
async def system_stats(
    _: None = Depends(verify_dev_password),
) -> dict[str, Any]:
    """Get real-time system statistics.

    Returns:
        Dictionary with counts for conversations, knowledge base,
        drafts, signals, and ChromaDB documents.
    """
    logger.info("Dev dashboard: system stats requested")

    async with await get_async_session() as session:
        total_conversations = await session.execute(
            select(func.count(Conversation.id))
        )
        total_knowledge = await session.execute(
            select(func.count(QAKnowledgeBase.id)).where(
                QAKnowledgeBase.is_active.is_(True)
            )
        )
        pending_drafts = await session.execute(
            select(func.count(QADraft.id)).where(QADraft.status == "pending")
        )
        approved_drafts = await session.execute(
            select(func.count(QADraft.id)).where(QADraft.status == "approved")
        )
        unprocessed_signals = await session.execute(
            select(func.count(QAMismatchSignal.id)).where(
                QAMismatchSignal.processed.is_(False)
            )
        )
        avg_confidence = await session.execute(
            select(func.avg(Conversation.confidence))
        )

    try:
        chroma_count = get_collection().count()
    except Exception:
        chroma_count = 0

    return {
        "conversations": total_conversations.scalar_one(),
        "knowledge_base": total_knowledge.scalar_one(),
        "pending_drafts": pending_drafts.scalar_one(),
        "approved_drafts": approved_drafts.scalar_one(),
        "unprocessed_signals": unprocessed_signals.scalar_one(),
        "avg_confidence": round(float(avg_confidence.scalar_one() or 0), 4),
        "chromadb_documents": chroma_count,
        "nightly_learning_enabled": settings.nightly_learning_enabled,
    }


# ---------------------------------------------------------------------------
# Configuration View
# ---------------------------------------------------------------------------


@router.get("/system/config")
async def system_config(
    _: None = Depends(verify_dev_password),
) -> dict[str, Any]:
    """Get current system configuration (non-sensitive values).

    Returns:
        Dictionary with model names, thresholds, and feature schedule.
    """
    return {
        "environment": settings.environment,
        "models": {
            "fast": settings.claude_model_fast,
            "smart": settings.claude_model_smart,
            "embedding": settings.embedding_model,
        },
        "thresholds": {
            "confidence_direct": settings.confidence_threshold_direct,
            "confidence_smart": settings.confidence_threshold_smart,
            "max_tokens": settings.max_tokens,
        },
        "learning": {
            "min_cluster_size": settings.min_pattern_cluster_size,
            "auto_draft_threshold": settings.auto_draft_threshold,
            "nightly_enabled": settings.nightly_learning_enabled,
            "nightly_hour": settings.nightly_learning_hour,
        },
        "languages": {
            "supported": settings.get_supported_languages_list(),
            "default": settings.default_language,
        },
        "feature_schedule": {
            "multilingual": settings.feature_multilingual_date,
            "b2b": settings.feature_b2b_date,
            "calculator": settings.feature_calculator_date,
            "youtube": settings.feature_youtube_date,
            "crm": settings.feature_crm_date,
        },
    }
