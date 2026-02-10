"""Utility helper functions for the chatbot application.

Provides language detection, text processing, ID generation,
and other shared utility functions.
"""

import hashlib
import uuid
from datetime import datetime, timezone

from langdetect import detect, LangDetectException

from app.config import settings
from app.utils.logger import logger


def detect_language(text: str) -> str:
    """Detect the language of input text.

    Uses langdetect library with fallback to default language.
    Maps detected language to supported languages list.

    Args:
        text: Input text to detect language for.

    Returns:
        Detected language code (nl, fr, en, da) or default language.
    """
    if not text or len(text.strip()) < 3:
        return settings.default_language

    try:
        detected = detect(text)
        supported = settings.get_supported_languages_list()

        if detected in supported:
            return detected

        language_map = {
            "af": "nl",
            "de": "nl",
            "nb": "da",
            "no": "da",
            "sv": "da",
        }

        mapped = language_map.get(detected, settings.default_language)
        return mapped if mapped in supported else settings.default_language

    except LangDetectException:
        logger.warning("Language detection failed for text: %s...", text[:50])
        return settings.default_language


def generate_session_id() -> str:
    """Generate a unique session ID.

    Returns:
        A UUID4-based session identifier string.
    """
    return str(uuid.uuid4())


def generate_chromadb_id(category: str, question: str) -> str:
    """Generate a deterministic ChromaDB document ID.

    Creates a consistent hash-based ID from category and question
    so that re-vectorizing the same Q&A yields the same ID.

    Args:
        category: The Q&A category.
        question: The question text.

    Returns:
        A hex digest string suitable as a ChromaDB document ID.
    """
    content = f"{category}:{question}".lower().strip()
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def truncate_text(text: str, max_length: int = 500) -> str:
    """Truncate text to a maximum length with ellipsis.

    Args:
        text: Text to truncate.
        max_length: Maximum character length.

    Returns:
        Truncated text with '...' appended if it exceeded max_length.
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def now_utc() -> datetime:
    """Return current UTC datetime.

    Returns:
        Current datetime in UTC timezone.
    """
    return datetime.utcnow()


def calculate_iso_week(dt: datetime) -> int:
    """Calculate ISO week number from a datetime.

    Args:
        dt: The datetime to get the week number for.

    Returns:
        ISO week number (1-53).
    """
    return dt.isocalendar()[1]
