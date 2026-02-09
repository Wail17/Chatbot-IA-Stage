"""FastAPI application entry point.

Initializes the application, configures CORS, registers routes,
and sets up logging and scheduled tasks.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import register_routes
from app.config import settings
from app.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup and shutdown events.

    Args:
        app: The FastAPI application instance.
    """
    logger.info("Starting Chatbot IA - Environment: %s", settings.environment)
    logger.info("Active features: %s", settings.get_active_features())
    logger.info("Supported languages: %s", settings.get_supported_languages_list())

    yield

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
