"""Feature flag management with database-backed manual overrides.

Priority order for determining if a feature is enabled:
1. Manual override in feature_flag_overrides table (highest priority)
2. Date-based activation from settings (feature_{name}_date)
3. Default: disabled

This allows developers to test features before their scheduled release
date or temporarily disable features that are causing issues.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select, update

from app.config import settings
from app.models.database import FeatureFlagOverride
from app.services.vectorstore import get_async_session
from app.utils.logger import logger

KNOWN_FEATURES = ["multilingual", "b2b", "calculator", "youtube", "crm"]


async def is_feature_enabled(feature_name: str) -> bool:
    """Check if a feature is enabled, respecting manual overrides.

    Priority: Manual DB override > Date-based auto-activation > False.

    Args:
        feature_name: Feature name (e.g., 'multilingual', 'b2b').

    Returns:
        True if the feature is enabled.
    """
    async with await get_async_session() as session:
        result = await session.execute(
            select(FeatureFlagOverride).where(
                FeatureFlagOverride.feature_name == feature_name
            )
        )
        override = result.scalar_one_or_none()

        if override is not None:
            return override.enabled

    return settings.is_feature_enabled(feature_name)


async def set_feature_override(
    feature_name: str,
    enabled: bool,
    override_by: str,
    notes: str = "",
) -> dict[str, Any]:
    """Create or update a manual feature flag override.

    Args:
        feature_name: Feature name to override.
        enabled: Whether to enable or disable the feature.
        override_by: Developer name who is setting the override.
        notes: Reason for the override.

    Returns:
        Dictionary with the override details.

    Raises:
        ValueError: If the feature name is not recognized.
    """
    if feature_name not in KNOWN_FEATURES:
        raise ValueError(
            f"Unknown feature '{feature_name}'. Known features: {KNOWN_FEATURES}"
        )

    now = datetime.now(timezone.utc)

    async with await get_async_session() as session:
        async with session.begin():
            result = await session.execute(
                select(FeatureFlagOverride).where(
                    FeatureFlagOverride.feature_name == feature_name
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                await session.execute(
                    update(FeatureFlagOverride)
                    .where(FeatureFlagOverride.feature_name == feature_name)
                    .values(
                        enabled=enabled,
                        override_by=override_by,
                        override_at=now,
                        notes=notes,
                    )
                )
            else:
                session.add(
                    FeatureFlagOverride(
                        feature_name=feature_name,
                        enabled=enabled,
                        override_by=override_by,
                        override_at=now,
                        notes=notes,
                    )
                )

    logger.info(
        "Feature override set: %s=%s by %s (%s)",
        feature_name,
        enabled,
        override_by,
        notes,
    )

    return {
        "feature_name": feature_name,
        "enabled": enabled,
        "override_by": override_by,
        "override_at": now.isoformat(),
        "notes": notes,
    }


async def remove_feature_override(feature_name: str) -> dict[str, str]:
    """Remove a manual override, reverting to date-based activation.

    Args:
        feature_name: Feature name to remove the override for.

    Returns:
        Dictionary confirming removal.
    """
    async with await get_async_session() as session:
        async with session.begin():
            await session.execute(
                delete(FeatureFlagOverride).where(
                    FeatureFlagOverride.feature_name == feature_name
                )
            )

    logger.info("Feature override removed: %s (reverted to date-based)", feature_name)

    return {
        "status": "removed",
        "feature_name": feature_name,
        "now_using": "date_based",
    }


async def get_all_feature_status() -> dict[str, dict[str, Any]]:
    """Get the status of all feature flags with their source.

    Returns:
        Dictionary keyed by feature name, each containing:
        - enabled: bool
        - source: 'manual_override' | 'date_based' | 'not_released'
        - Additional metadata depending on source.
    """
    status: dict[str, dict[str, Any]] = {}

    async with await get_async_session() as session:
        result = await session.execute(select(FeatureFlagOverride))
        overrides = {o.feature_name: o for o in result.scalars().all()}

    for feature in KNOWN_FEATURES:
        override = overrides.get(feature)

        if override:
            status[feature] = {
                "enabled": override.enabled,
                "source": "manual_override",
                "override_by": override.override_by,
                "override_at": override.override_at.isoformat()
                if override.override_at
                else None,
                "notes": override.notes,
            }
        else:
            date_enabled = settings.is_feature_enabled(feature)
            release_date = getattr(settings, f"feature_{feature}_date", None)

            status[feature] = {
                "enabled": date_enabled,
                "source": "date_based" if date_enabled else "not_released",
                "release_date": release_date,
            }

    return status
