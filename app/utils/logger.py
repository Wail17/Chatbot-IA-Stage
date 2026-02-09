"""Centralized logging configuration.

Provides a structured logger with appropriate formatting for both
development (human-readable) and production (JSON-structured) environments.
"""

import logging
import sys
from typing import Optional

from app.config import settings


def setup_logger(name: Optional[str] = None, level: Optional[int] = None) -> logging.Logger:
    """Create and configure a logger instance.

    Args:
        name: Logger name. Uses root logger name if not provided.
        level: Logging level. Defaults based on environment setting.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name or "chatbot")

    if logger.handlers:
        return logger

    if level is None:
        level = logging.DEBUG if settings.debug else logging.INFO

    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    if settings.environment == "production":
        formatter = logging.Formatter(
            '{"timestamp":"%(asctime)s","level":"%(levelname)s",'
            '"module":"%(module)s","message":"%(message)s"}'
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s:%(module)s:%(lineno)d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


logger = setup_logger("chatbot")
