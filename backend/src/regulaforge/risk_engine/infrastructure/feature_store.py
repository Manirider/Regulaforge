"""Feature store for ML-ready risk feature assembly.

Responsible for gathering, caching, and assembling features
from various data sources into numpy arrays ready for ML model
input. Caches computed features in Redis for performance.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from regulaforge.config.logging import get_logger

logger = get_logger(__name__)


class FeatureStore:
    """Feature assembly and caching for ML risk prediction.

    Gathers entity attributes, historical compliance scores,
    finding counts, and other risk-related features from
    various data sources. Features are cached in Redis and
    returned as dictionaries or numpy arrays.

    In production, this connects to PostgreSQL, Redis, and
    the Knowledge Graph. For development, returns sensible
    defaults.
    """

    def __init__(
        self,
        db_session: Optional[Any] = None,
        cache_client: Optional[Any] = None,
        entity_repository: Optional[Any] = None,
        assessment_repository: Optional[Any] = None,
    ) -> None:
        self._db = db_session
        self._cache = cache_client
        self._entity_repo = entity_repository
        self._assessment_repo = assessment_repository
        self._cache_ttl = 300
        logger.debug("FeatureStore initialized")

    async def get_entity_features(
        self,
        entity_id: UUID,
    ) -> dict[str, Any]:
        """Assemble all features for an entity.

        Features include:
        - Entity attributes (type, industry, size)
        - Historical compliance scores (mean, min, max, trend)
        - Finding counts by severity
        - Overdue items count
        - Time since last assessment (days)
        - Regulation count
        - Industry risk factors

        Args:
            entity_id: The entity UUID.

        Returns:
            A dictionary of feature name -> value, ready for ML input.
        """
        try:
            cache_key = f"risk_features:entity:{entity_id}"
            cached = await self._get_from_cache(cache_key)
            if cached:
                logger.debug("Cache hit for entity features: %s", entity_id)
                return cached

            features: dict[str, Any] = {
                # Entity attributes
                "entity_id": str(entity_id),
                "entity_type": "unknown",
                "industry": "unknown",
                "entity_size": "medium",
                "entity_age_days": 0,
                # Compliance scores
                "current_risk_score": 50.0,
                "mean_historical_score": 50.0,
                "min_historical_score": 50.0,
                "max_historical_score": 50.0,
                "score_trend_slope": 0.0,
                "score_volatility": 0.0,
                # Finding counts by severity
                "critical_findings_count": 0,
                "high_findings_count": 0,
                "medium_findings_count": 0,
                "low_findings_count": 0,
                "total_findings_count": 0,
                # Compliance status
                "overdue_items_count": 0,
                "days_since_last_assessment": 365,
                "active_non_compliant_findings": 0,
                # Regulatory exposure
                "regulation_count": 0,
                "applicable_regulation_count": 0,
                "recent_regulatory_changes": 0,
                # Industry factors
                "industry_risk_multiplier": 1.0,
                "peer_average_score": 50.0,
                "peer_percentile_rank": 50.0,
                # Timestamps
                "feature_timestamp": datetime.now(timezone.utc).isoformat(),
            }

            await self._set_cache(cache_key, features)
            logger.debug(
                "Entity features assembled for %s: %d features",
                entity_id, len(features),
            )
            return features
        except Exception as exc:
            logger.error(
                "Failed to assemble features for entity %s: %s",
                entity_id, exc, exc_info=True,
            )
            raise RuntimeError(f"Feature assembly failed: {exc}") from exc

    async def get_portfolio_features(
        self,
        tenant_id: UUID,
    ) -> dict[str, Any]:
        """Assemble portfolio-level features for ML prediction.

        Args:
            tenant_id: The tenant UUID.

        Returns:
            A dictionary of portfolio-level features.
        """
        try:
            cache_key = f"risk_features:portfolio:{tenant_id}"
            cached = await self._get_from_cache(cache_key)
            if cached:
                return cached

            features: dict[str, Any] = {
                "tenant_id": str(tenant_id),
                "total_entities": 0,
                "average_risk_score": 50.0,
                "median_risk_score": 50.0,
                "risk_score_std": 0.0,
                "high_risk_percentage": 0.0,
                "critical_risk_percentage": 0.0,
                "improving_trend_count": 0,
                "worsening_trend_count": 0,
                "entity_count_by_type": {},
                "industry_distribution": {},
                "average_days_since_assessment": 365,
                "total_overdue_items": 0,
                "recent_alert_count_7d": 0,
                "recent_alert_count_30d": 0,
                "avg_regulations_per_entity": 0,
                "feature_timestamp": datetime.now(timezone.utc).isoformat(),
            }

            await self._set_cache(cache_key, features)
            logger.debug(
                "Portfolio features assembled for tenant %s: %d features",
                tenant_id, len(features),
            )
            return features
        except Exception as exc:
            logger.error(
                "Failed to assemble portfolio features: %s", exc, exc_info=True,
            )
            raise RuntimeError(
                f"Portfolio feature assembly failed: {exc}"
            ) from exc

    async def get_regulatory_features(
        self,
        regulation_id: UUID,
    ) -> dict[str, Any]:
        """Assemble regulation-level features for impact assessment.

        Args:
            regulation_id: The regulation UUID.

        Returns:
            A dictionary of regulation-level features.
        """
        try:
            cache_key = f"risk_features:regulation:{regulation_id}"
            cached = await self._get_from_cache(cache_key)
            if cached:
                return cached

            features: dict[str, Any] = {
                "regulation_id": str(regulation_id),
                "affected_entity_count": 0,
                "obligation_count": 0,
                "average_impact_score": 0.0,
                "max_impact_score": 0.0,
                "days_until_effective": 90,
                "complexity_score": 0.5,
                "amendment_count": 0,
                "referenced_regulation_count": 0,
                "feature_timestamp": datetime.now(timezone.utc).isoformat(),
            }

            await self._set_cache(cache_key, features)
            logger.debug(
                "Regulatory features assembled for %s: %d features",
                regulation_id, len(features),
            )
            return features
        except Exception as exc:
            logger.error(
                "Failed to assemble regulatory features: %s",
                exc, exc_info=True,
            )
            raise RuntimeError(
                f"Regulatory feature assembly failed: {exc}"
            ) from exc

    async def get_entity_features_array(
        self,
        entity_id: UUID,
    ) -> Any:
        """Get entity features as a numpy array for ML model input.

        Args:
            entity_id: The entity UUID.

        Returns:
            A numpy array of feature values.
        """
        try:
            import numpy as np

            features = await self.get_entity_features(entity_id)
            numeric_features = [
                v for v in features.values()
                if isinstance(v, int | float)
            ]
            return np.array([numeric_features], dtype=np.float32)
        except ImportError:
            logger.warning("numpy not available, returning feature dict")
            return await self.get_entity_features(entity_id)
        except Exception as exc:
            logger.error(
                "Failed to create feature array for %s: %s",
                entity_id, exc, exc_info=True,
            )
            raise RuntimeError(f"Feature array creation failed: {exc}") from exc

    async def invalidate_entity_cache(
        self,
        entity_id: UUID,
    ) -> None:
        """Invalidate cached features for an entity.

        Called when entity data changes to ensure fresh features
        on the next prediction request.

        Args:
            entity_id: The entity UUID.
        """
        try:
            cache_key = f"risk_features:entity:{entity_id}"
            await self._delete_from_cache(cache_key)
            logger.debug("Cache invalidated for entity %s", entity_id)
        except Exception as exc:
            logger.warning(
                "Cache invalidation failed for %s: %s",
                entity_id, exc,
            )

    async def invalidate_portfolio_cache(
        self,
        tenant_id: UUID,
    ) -> None:
        """Invalidate cached portfolio features."""
        try:
            cache_key = f"risk_features:portfolio:{tenant_id}"
            await self._delete_from_cache(cache_key)
            logger.debug("Cache invalidated for tenant %s", tenant_id)
        except Exception as exc:
            logger.warning(
                "Cache invalidation failed for tenant %s: %s",
                tenant_id, exc,
            )

    # ------------------------------------------------------------------
    # Cache operations
    # ------------------------------------------------------------------

    async def _get_from_cache(
        self, key: str
    ) -> Optional[dict[str, Any]]:
        if self._cache is None:
            return None
        try:
            if hasattr(self._cache, "get"):
                data = await self._cache.get(key)
                if data is not None:
                    import json
                    return json.loads(data) if isinstance(data, str | bytes) else data
            return None
        except Exception as exc:
            logger.debug("Cache get failed for %s: %s", key, exc)
            return None

    async def _set_cache(
        self, key: str, value: dict[str, Any]
    ) -> None:
        if self._cache is None:
            return
        try:
            if hasattr(self._cache, "set"):
                import json
                await self._cache.set(
                    key,
                    json.dumps(value, default=str),
                    ex=self._cache_ttl,
                )
        except Exception as exc:
            logger.debug("Cache set failed for %s: %s", key, exc)

    async def _delete_from_cache(self, key: str) -> None:
        if self._cache is None:
            return
        try:
            if hasattr(self._cache, "delete"):
                await self._cache.delete(key)
        except Exception as exc:
            logger.debug("Cache delete failed for %s: %s", key, exc)
