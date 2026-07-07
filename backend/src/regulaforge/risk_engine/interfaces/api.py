"""Risk Prediction Engine API endpoints.

Exposes risk calculation, prediction, monitoring, and alert
management as RESTful endpoints. No business logic — all
operations are delegated to application layer services.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from regulaforge.config.constants import (
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_500_INTERNAL_SERVER_ERROR,
    MAX_PAGE_SIZE,
)
from regulaforge.interfaces.api.middleware.auth_middleware import get_current_user
from regulaforge.risk_engine.application.risk_calculator import RiskCalculator
from regulaforge.risk_engine.application.risk_monitor import RiskMonitor
from regulaforge.risk_engine.application.risk_predictor import RiskPredictor

router = APIRouter(
    prefix="/risk",
    tags=["Risk Engine"],
    dependencies=[Depends(get_current_user)],
)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

from pydantic import BaseModel, Field  # noqa: E402


class RiskAssessmentRequest(BaseModel):
    """Request to calculate risk for a completed assessment."""

    assessment_id: str = Field(..., description="UUID of the completed assessment")


class RiskPredictRequest(BaseModel):
    """Request for ML-based risk prediction."""

    entity_id: str = Field(..., description="UUID of the entity to predict")


class AcknowledgeAlertRequest(BaseModel):
    """Request to acknowledge a risk alert."""

    user_id: str = Field(..., description="UUID of the acknowledging user")


class ResolveAlertRequest(BaseModel):
    """Request to resolve a risk alert."""

    resolution_notes: Optional[str] = Field(default=None, description="Resolution notes")


class RiskScoreResponse(BaseModel):
    """Response schema for a risk score."""

    id: str
    entity_id: str
    assessment_id: Optional[str] = None
    overall_score: float
    category_scores: dict[str, float]
    risk_level: str
    confidence_interval: Optional[list[float]] = None
    prediction_date: str
    model_version: str
    features_used: list[str]


class RiskProfileResponse(BaseModel):
    """Response schema for a full risk profile."""

    entity_id: str
    entity_type: str
    current_score: RiskScoreResponse
    risk_factors: list[dict[str, Any]]
    historical_trend: Optional[dict[str, Any]] = None
    peer_comparison: dict[str, Any]
    regulatory_changes_impact: dict[str, Any]
    recommendations: list[str]


class PortfolioRiskResponse(BaseModel):
    """Response schema for portfolio risk summary."""

    total_entities: int
    risk_distribution: dict[str, int]
    average_score: float
    high_risk_count: int
    critical_risk_count: int
    top_risk_factors: list[dict[str, Any]]
    trend_summary: Optional[dict[str, Any]] = None


class RiskTrendResponse(BaseModel):
    """Response schema for risk trend."""

    entity_id: str
    risk_scores_over_time: list[dict[str, Any]]
    trend_direction: str
    volatility: float
    seasonality: Optional[dict[str, Any]] = None
    forecast: list[dict[str, Any]]


class RiskAlertResponse(BaseModel):
    """Response schema for a risk alert."""

    id: str
    entity_id: str
    alert_type: str
    severity: str
    message: str
    details: dict[str, Any]
    triggered_at: str
    acknowledged_at: Optional[str] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[str] = None
    is_active: bool
    is_acknowledged: bool


class RiskAlertListResponse(BaseModel):
    """Response schema for a list of alerts."""

    items: list[RiskAlertResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class RegulatoryImpactResponse(BaseModel):
    """Response schema for regulatory change impact."""

    regulation_id: str
    regulation_title: str
    change_description: str
    effective_date: str
    impacted_entities: list[str]
    risk_score_delta: float
    affected_obligations: list[str]
    recommended_actions: list[str]


class EmergingRisksResponse(BaseModel):
    """Response schema for emerging risks scan."""

    alerts: list[RiskAlertResponse]
    scan_timestamp: str
    total_alerts: int


# ---------------------------------------------------------------------------
# Dependency injection helpers
# ---------------------------------------------------------------------------


async def get_risk_calculator() -> RiskCalculator:
    return RiskCalculator()


async def get_risk_predictor() -> RiskPredictor:
    return RiskPredictor()


async def get_risk_monitor() -> RiskMonitor:
    return RiskMonitor()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/assess", response_model=RiskScoreResponse, status_code=status.HTTP_200_OK)
async def calculate_assessment_risk(
    request: RiskAssessmentRequest,
    calculator: RiskCalculator = Depends(get_risk_calculator),  # noqa: B008
) -> Any:
    """Calculate risk score for a completed compliance assessment."""
    try:

        from regulaforge.infrastructure.persistence.database import get_session

        async with get_session() as session:
            from regulaforge.domain.repositories.assessment_repository import SqlAlchemyAssessmentRepository
            repo = SqlAlchemyAssessmentRepository(session)
            assessment = await repo.get_by_id(UUIDType(request.assessment_id))  # noqa: F821

        if not assessment:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"Assessment '{request.assessment_id}' not found",
            )

        risk_score = calculator.calculate_assessment_risk(assessment)
        return _risk_score_to_response(risk_score)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/entities/{entity_id}/profile", response_model=RiskProfileResponse)
async def get_entity_risk_profile(
    entity_id: UUID,
    as_of: Optional[str] = Query(default=None, description="ISO 8601 point-in-time"),
    calculator: RiskCalculator = Depends(get_risk_calculator),  # noqa: B008
) -> Any:
    """Get full risk profile for an entity."""
    try:
        as_of_dt = datetime.fromisoformat(as_of) if as_of else None
        profile = calculator.calculate_entity_risk(entity_id, as_of=as_of_dt)
        return _profile_to_response(profile)
    except ValueError as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/entities/{entity_id}/trend", response_model=RiskTrendResponse)
async def get_entity_risk_trend(
    entity_id: UUID,
    lookback_days: int = Query(default=90, ge=1, le=365, description="Days of history"),
    predictor: RiskPredictor = Depends(get_risk_predictor),  # noqa: B008
) -> Any:
    """Get risk trend with forecast for an entity."""
    try:
        trend = await predictor.get_risk_trend(entity_id, lookback_days=lookback_days)
        return _trend_to_response(trend)
    except ValueError as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/entities/{entity_id}/alerts", response_model=RiskAlertListResponse)
async def get_entity_alerts(
    entity_id: UUID,
    page: int = Query(default=DEFAULT_PAGE, ge=1, description="Page number"),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    monitor: RiskMonitor = Depends(get_risk_monitor),  # noqa: B008
) -> Any:
    """Get active alerts for an entity."""
    try:
        alerts = await monitor.get_active_alerts(entity_id=entity_id)
        total = len(alerts)
        offset = (page - 1) * page_size
        page_items = alerts[offset:offset + page_size]
        total_pages = max(1, -(-total // page_size))

        return RiskAlertListResponse(
            items=[RiskAlertResponse(**alert.to_dict()) for alert in page_items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    except ValueError as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/portfolio", response_model=PortfolioRiskResponse)
async def get_portfolio_risk(
    tenant_id: Optional[str] = Query(default=None, description="Tenant UUID"),
    entity_type: Optional[str] = Query(default=None, description="Filter by entity type"),
    calculator: RiskCalculator = Depends(get_risk_calculator),  # noqa: B008
) -> Any:
    """Get portfolio-level risk summary."""
    try:
        filters = {}
        if entity_type:
            filters["entity_type"] = entity_type
        tid = UUIDType(tenant_id) if tenant_id else UUIDType(int=0)  # noqa: F821
        summary = calculator.calculate_portfolio_risk(tid, filters=filters)
        return _portfolio_to_response(summary)
    except ValueError as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/predict", response_model=RiskScoreResponse)
async def predict_entity_risk(
    request: RiskPredictRequest,
    predictor: RiskPredictor = Depends(get_risk_predictor),  # noqa: B008
) -> Any:
    """Predict future risk score for an entity using ML."""
    try:
        entity_id = UUIDType(request.entity_id)  # noqa: F821
        prediction = await predictor.predict_entity_risk(entity_id)
        return _risk_score_to_response(prediction)
    except ValueError as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/alerts/{alert_id}/acknowledge", response_model=RiskAlertResponse)
async def acknowledge_alert(
    alert_id: UUID,
    request: AcknowledgeAlertRequest,
    monitor: RiskMonitor = Depends(get_risk_monitor),  # noqa: B008
) -> Any:
    """Acknowledge a risk alert."""
    try:
        alert = await monitor.acknowledge_alert(alert_id, UUIDType(request.user_id))  # noqa: F821
        return RiskAlertResponse(**alert.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/alerts/{alert_id}/resolve", response_model=RiskAlertResponse)
async def resolve_alert(
    alert_id: UUID,
    request: ResolveAlertRequest,
    monitor: RiskMonitor = Depends(get_risk_monitor),  # noqa: B008
) -> Any:
    """Resolve a risk alert."""
    try:
        alert = await monitor.resolve_alert(alert_id, resolution_notes=request.resolution_notes)
        return RiskAlertResponse(**alert.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/regulatory-impact/{regulation_id}", response_model=RegulatoryImpactResponse)
async def get_regulatory_impact(
    regulation_id: UUID,
    calculator: RiskCalculator = Depends(get_risk_calculator),  # noqa: B008
) -> Any:
    """Get risk impact of a regulatory change."""
    try:
        impact = calculator.calculate_regulatory_change_impact(regulation_id)
        return _impact_to_response(impact)
    except ValueError as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/emerging-risks", response_model=EmergingRisksResponse)
async def get_emerging_risks(
    tenant_id: Optional[str] = Query(default=None, description="Tenant UUID"),
    predictor: RiskPredictor = Depends(get_risk_predictor),  # noqa: B008
) -> Any:
    """Identify emerging risk patterns and early warnings."""
    try:
        tid = UUIDType(tenant_id) if tenant_id else UUIDType(int=0)  # noqa: F821
        alerts = await predictor.identify_emerging_risks(tid)
        return EmergingRisksResponse(
            alerts=[RiskAlertResponse(**alert.to_dict()) for alert in alerts],
            scan_timestamp=datetime.now().isoformat(),
            total_alerts=len(alerts),
        )
    except ValueError as e:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def _risk_score_to_response(score: Any) -> dict[str, Any]:
    data = score.to_dict() if hasattr(score, "to_dict") else score
    if isinstance(data, dict):
        ci = data.get("confidence_interval")
        return RiskScoreResponse(
            id=data["id"],
            entity_id=data["entity_id"],
            assessment_id=data.get("assessment_id"),
            overall_score=data["overall_score"],
            category_scores=data["category_scores"],
            risk_level=data["risk_level"],
            confidence_interval=list(ci) if ci else None,
            prediction_date=data["prediction_date"],
            model_version=data["model_version"],
            features_used=data["features_used"],
        )
    return RiskScoreResponse(
        id=str(score.id),
        entity_id=str(score.entity_id),
        assessment_id=str(score.assessment_id) if score.assessment_id else None,
        overall_score=score.overall_score,
        category_scores=score.category_scores,
        risk_level=score.risk_level.value,
        confidence_interval=list(score.confidence_interval) if score.confidence_interval else None,
        prediction_date=score.prediction_date.isoformat(),
        model_version=score.model_version,
        features_used=score.features_used,
    )


def _profile_to_response(profile: Any) -> dict[str, Any]:
    data = profile.to_dict() if hasattr(profile, "to_dict") else profile
    if isinstance(data, dict):
        return RiskProfileResponse(**data)
    return RiskProfileResponse(
        entity_id=str(profile.entity_id),
        entity_type=profile.entity_type,
        current_score=_risk_score_to_response(profile.current_score),
        risk_factors=[f.to_dict() for f in profile.risk_factors],
        historical_trend=profile.historical_trend.to_dict() if profile.historical_trend else None,
        peer_comparison=profile.peer_comparison,
        regulatory_changes_impact=profile.regulatory_changes_impact,
        recommendations=profile.recommendations,
    )


def _trend_to_response(trend: Any) -> dict[str, Any]:
    data = trend.to_dict() if hasattr(trend, "to_dict") else trend
    if isinstance(data, dict):
        return RiskTrendResponse(**data)
    return RiskTrendResponse(
        entity_id=str(trend.entity_id),
        risk_scores_over_time=trend.risk_scores_over_time,
        trend_direction=trend.trend_direction,
        volatility=trend.volatility,
        seasonality=trend.seasonality,
        forecast=trend.forecast,
    )


def _portfolio_to_response(summary: Any) -> dict[str, Any]:
    data = summary.to_dict() if hasattr(summary, "to_dict") else summary
    if isinstance(data, dict):
        return PortfolioRiskResponse(**data)
    return PortfolioRiskResponse(
        total_entities=summary.total_entities,
        risk_distribution=summary.risk_distribution,
        average_score=summary.average_score,
        high_risk_count=summary.high_risk_count,
        critical_risk_count=summary.critical_risk_count,
        top_risk_factors=summary.top_risk_factors,
        trend_summary=summary.trend_summary,
    )


def _impact_to_response(impact: Any) -> dict[str, Any]:
    data = impact.to_dict() if hasattr(impact, "to_dict") else impact
    if isinstance(data, dict):
        return RegulatoryImpactResponse(**data)
    return RegulatoryImpactResponse(
        regulation_id=str(impact.regulation_id),
        regulation_title=impact.regulation_title,
        change_description=impact.change_description,
        effective_date=impact.effective_date.isoformat(),
        impacted_entities=[str(eid) for eid in impact.impacted_entities],
        risk_score_delta=impact.risk_score_delta,
        affected_obligations=impact.affected_obligations,
        recommended_actions=impact.recommended_actions,
    )
