"""Application configuration with dynamic Feature Flags system.

Feature flags are date-based with manual override support via environment
variables. This enables progressive feature activation week by week during
the 14-week internship period.
"""

import os
from datetime import date, datetime
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Attributes:
        anthropic_api_key: Anthropic API key for Claude models.
        openai_api_key: OpenAI API key for embeddings.
        database_url: PostgreSQL connection string.
        environment: Runtime environment (development/staging/production).
        secret_key: Application secret key for signing.
        debug: Enable debug mode.
    """

    # API Keys
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # Database
    database_url: str = "postgresql://localhost:5432/chatbot_db"

    # App
    environment: str = "development"
    secret_key: str = "change-me-in-production"
    debug: bool = True

    # AI Settings
    embedding_model: str = "text-embedding-3-small"
    claude_model_fast: str = "claude-haiku-4-20250514"
    claude_model_smart: str = "claude-sonnet-4-20250514"

    # Thresholds
    confidence_threshold_direct: float = 0.85
    confidence_threshold_smart: float = 0.60
    max_tokens: int = 1000

    # Languages
    supported_languages: str = "nl,fr,en,da"
    default_language: str = "nl"

    # Feature Flags Dates (ISO format YYYY-MM-DD)
    feature_multilingual_date: str = "2025-03-14"
    feature_b2b_date: str = "2025-03-28"
    feature_calculator_date: str = "2025-04-18"
    feature_youtube_date: str = "2025-05-02"
    feature_crm_date: str = "2025-05-22"

    # Dev Dashboard
    dev_password: str = "dev123"

    # Learning Engine
    min_pattern_cluster_size: int = 5
    auto_draft_threshold: float = 0.80
    nightly_learning_enabled: bool = True
    nightly_learning_hour: int = 2

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
    }

    def is_feature_enabled(self, feature_name: str) -> bool:
        """Check if a feature is enabled based on date or manual override.

        Priority order:
        1. Manual override via FEATURE_{NAME}_ENABLED=true env var
        2. Date-based activation from feature_{name}_date setting

        Args:
            feature_name: Name of the feature (e.g., "multilingual", "b2b").

        Returns:
            True if the feature is currently enabled, False otherwise.
        """
        override_key = f"FEATURE_{feature_name.upper()}_ENABLED"
        override_value = os.getenv(override_key, "").lower()
        if override_value == "true":
            return True
        if override_value == "false":
            return False

        date_key = f"feature_{feature_name.lower()}_date"
        release_date_str: Optional[str] = getattr(self, date_key, None)

        if not release_date_str:
            return False

        release_date = datetime.strptime(release_date_str, "%Y-%m-%d").date()
        today = date.today()

        return today >= release_date

    def get_supported_languages_list(self) -> list[str]:
        """Return supported languages as a list.

        Returns:
            List of language codes.
        """
        return [lang.strip() for lang in self.supported_languages.split(",")]

    def get_active_features(self) -> dict[str, bool]:
        """Return status of all feature flags.

        Returns:
            Dictionary mapping feature names to their enabled status.
        """
        features = ["multilingual", "b2b", "calculator", "youtube", "crm"]
        return {name: self.is_feature_enabled(name) for name in features}


settings = Settings()
