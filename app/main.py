"""FastAPI application entry point.

Initializes the application, configures CORS, registers routes,
sets up static file serving for the admin dashboard, and manages
the background task scheduler.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import register_routes
from app.config import settings
from app.utils.logger import logger

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup and shutdown events.

    Startup:
    - Logs configuration
    - Starts APScheduler for nightly learning (if enabled)

    Shutdown:
    - Stops APScheduler gracefully

    Args:
        app: The FastAPI application instance.
    """
    logger.info("Starting Chatbot IA - Environment: %s", settings.environment)
    logger.info("Active features: %s", settings.get_active_features())
    logger.info("Supported languages: %s", settings.get_supported_languages_list())

    if settings.nightly_learning_enabled:
        from app.tasks import start_scheduler

        start_scheduler()
        logger.info("Nightly learning scheduler enabled")

    yield

    from app.tasks import stop_scheduler

    stop_scheduler()
    logger.info("Shutting down Chatbot IA")


app = FastAPI(
    title="Zwembad.eu AI Chatbot",
    description=(
        "Intelligent chatbot with Human-in-the-Loop learning system "
        "for zwembad.eu swimming pool expertise."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://zwembad.eu",
        "https://www.zwembad.eu",
        "http://localhost:3000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

register_routes(app)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
