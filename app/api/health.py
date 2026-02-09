"""Health check endpoint.

Provides a simple health check for monitoring and Railway deployment.
"""

from fastapi import APIRouter

from app.config import settings
from app.models.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Check application health and return active feature flags.

    Returns:
        HealthResponse with status, environment, and active features.
    """
    return HealthResponse(
        status="healthy",
        environment=settings.environment,
        features=settings.get_active_features(),
        version="1.0.0",
    )
