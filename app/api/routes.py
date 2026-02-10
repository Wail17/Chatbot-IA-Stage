"""API route registration.

Centralizes all route registration to keep main.py clean.
Each router module handles its own endpoint group.
"""

from fastapi import FastAPI

from app.api.chat import router as chat_router
from app.api.admin import router as admin_router
from app.api.learning import router as learning_router
from app.api.health import router as health_router
from app.api.dev import router as dev_router


def register_routes(app: FastAPI) -> None:
    """Register all API routers with the application.

    Args:
        app: The FastAPI application instance.
    """
    app.include_router(health_router, tags=["Health"])
    app.include_router(chat_router, prefix="/api", tags=["Chat"])
    app.include_router(admin_router, prefix="/api/admin", tags=["Admin"])
    app.include_router(learning_router, prefix="/api/learning", tags=["Learning"])
    app.include_router(dev_router, prefix="/dev", tags=["Developer"])
