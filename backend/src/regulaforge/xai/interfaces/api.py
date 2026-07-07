"""FastAPI router for the Explainable AI (XAI) subsystem.

Provides RESTful endpoints for generating explanations, retrieving
counterfactuals, performing what-if analysis, comparing predictions,
and fetching visualization data. All business logic is delegated to
the ExplanationService in the application layer.
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field

from regulaforge.config.logging import get_logger
from regulaforge.interfaces.api.middleware.auth_middleware import get_current_user
from regulaforge.xai.application.explanation_service import ExplanationService
from regulaforge.xai.domain.models import (
    ExplanationRequest,
    ExplanationType,
)

logger = get_logger(__name__)

router = APIRouter(
    prefix="/xai",
    tags=["Explainable AI"],
    dependencies=[Depends(get_current_user)],
)

_service: Optional[ExplanationService] = None


def set_explanation_service(service: ExplanationService) -> None:
    """Set the global ExplanationService instance for the API router.

    Args:
        service: The ExplanationService instance to use.
    """
    global _service
    _service = service


def get_explanation_service() -> ExplanationService:
    """Dependency: get the current ExplanationService instance.

    Returns:
        The ExplanationService instance.

    Raises:
        HTTPException: If the service is not configured.
    """
    if _service is None:
        raise HTTPException(
            status_code=503,
            detail="Explanation service is not configured",
        )
    return _service


# ---------------------------------------------------------------------------
# Pydantic Request/Response Models
# ---------------------------------------------------------------------------


class ExplainRequest(BaseModel):
    prediction_id: str = Field(..., description="UUID of the prediction to explain")
    model_id: str = Field(..., description="Model identifier from the model registry")
    features: dict[str, float] = Field(..., description="Feature name to value mapping")
    feature_names: Optional[list[str]] = Field(None, description="Names of features in order")
    explanation_types: list[str] = Field(
        default=["shap", "lime"],
        description="Types of explanations to generate",
    )
    audience: str = Field(
        default="technical",
        description="Target audience: technical, compliance_officer, executive, regulator",
    )
    detail_level: str = Field(
        default="detailed",
        description="Detail level: basic, detailed, comprehensive",
    )
    include_visualizations: bool = Field(default=True, description="Include visualization data")
    max_features: int = Field(default=20, ge=1, le=100, description="Maximum features to return")
    language: str = Field(default="en", description="Language for natural language explanations")


class ExplainResponse(BaseModel):
    prediction_id: str
    explanations: list[dict[str, Any]]
    natural_language: Optional[dict[str, Any]] = None
    counterfactual: Optional[dict[str, Any]] = None
    visualizations: dict[str, Any] = Field(default_factory=dict)
    generated_at: str


class ExplanationResponse(BaseModel):
    id: str
    prediction_id: str
    model_name: str
    explanation_type: str
    features: list[dict[str, Any]]
    summary: str
    confidence: float
    visualization_data: dict[str, Any]
    timestamp: str
    metadata: dict[str, Any]


class CounterfactualRequest(BaseModel):
    model_id: str = Field(..., description="Model identifier from the model registry")
    X_sample: dict[str, float] = Field(..., description="Original input sample as feature dict")
    desired_outcome: float = Field(..., description="Desired target outcome")
    feature_ranges: Optional[dict[str, list[float]]] = Field(
        None,
        description="Feature bounds as {feature_name: [min, max]}",
    )


class CounterfactualResponse(BaseModel):
    id: str
    original_input: dict[str, Any]
    counterfactual_input: dict[str, Any]
    feature_changes: list[dict[str, Any]]
    outcome_change: str
    distance: float
    viability: float
    natural_language: str


class WhatIfRequest(BaseModel):
    model_id: str = Field(..., description="Model identifier from the model registry")
    X_sample: dict[str, float] = Field(..., description="Original input sample as feature dict")
    feature_changes: dict[str, float] = Field(
        ...,
        description="Feature changes as {feature_name_or_index: new_value}",
    )


class WhatIfResponse(BaseModel):
    original_input: dict[str, Any]
    modified_input: dict[str, Any]
    feature_changes: list[dict[str, Any]]


class CompareRequest(BaseModel):
    prediction_ids: list[str] = Field(..., description="List of prediction UUIDs to compare")
    model_id: str = Field(..., description="Model identifier from the model registry")


class FeatureImportanceResponse(BaseModel):
    feature_name: str
    importance: float
    abs_importance: float
    direction: str
    sample_count: int


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/explain",
    response_model=ExplainResponse,
    status_code=200,
    summary="Generate explanations for an AI prediction",
)
async def explain_prediction(
    request: ExplainRequest,
    service: ExplanationService = Depends(get_explanation_service),  # noqa: B008
) -> dict[str, Any]:
    try:
        exp_types: list[ExplanationType] = []
        for et_str in request.explanation_types:
            try:
                exp_types.append(ExplanationType(et_str.lower()))
            except ValueError:
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid explanation type: {et_str}. "
                           f"Valid types: {[t.value for t in ExplanationType]}",
                )

        exp_request = ExplanationRequest(
            prediction_id=UUID(request.prediction_id),
            explanation_types=exp_types,
            audience=request.audience,
            detail_level=request.detail_level,
            include_visualizations=request.include_visualizations,
            max_features=request.max_features,
            language=request.language,
        )

        result = await service.explain_prediction(
            model_id=request.model_id,
            features=request.features,
            feature_names=request.feature_names,
            request=exp_request,
        )
        return result
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    except Exception as exc:
        logger.error("Explanation generation failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Explanation failed: {exc}")


@router.get(
    "/explanations/{explanation_id}",
    response_model=ExplanationResponse,
    summary="Get a specific explanation by ID",
)
async def get_explanation(
    explanation_id: UUID = Path(..., description="UUID of the explanation"),  # noqa: B008
    service: ExplanationService = Depends(get_explanation_service),  # noqa: B008
) -> dict[str, Any]:
    explanation = await service.get_explanation(explanation_id)
    if explanation is None:
        raise HTTPException(
            status_code=404,
            detail=f"Explanation {explanation_id} not found",
        )
    return explanation.to_dict()


@router.get(
    "/predictions/{prediction_id}/explanations",
    summary="List all explanations for a given prediction",
)
async def get_prediction_explanations(
    prediction_id: UUID = Path(..., description="UUID of the prediction"),  # noqa: B008
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    service: ExplanationService = Depends(get_explanation_service),  # noqa: B008
) -> dict[str, Any]:
    try:
        explanations = []
        for exp in list(service._explanations.values()):
            if exp.prediction_id == prediction_id:
                explanations.append(exp.to_dict())
        return {
            "items": explanations,
            "total": len(explanations),
            "page": page,
            "page_size": page_size,
        }
    except Exception as exc:
        logger.error("Failed to get explanations for prediction %s: %s", prediction_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/counterfactual",
    response_model=CounterfactualResponse,
    status_code=200,
    summary="Generate a counterfactual explanation",
)
async def generate_counterfactual(
    request: CounterfactualRequest,
    service: ExplanationService = Depends(get_explanation_service),  # noqa: B008
) -> dict[str, Any]:
    try:
        feature_ranges = None
        if request.feature_ranges:
            feature_ranges = {
                k: (float(v[0]), float(v[1]))
                for k, v in request.feature_ranges.items()
                if len(v) == 2
            }

        result = await service.generate_counterfactual(
            model_id=request.model_id,
            X_sample=request.X_sample,
            desired_outcome=request.desired_outcome,
            feature_ranges=feature_ranges,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("Counterfactual generation failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/what-if",
    response_model=WhatIfResponse,
    status_code=200,
    summary="Perform what-if analysis by modifying features",
)
async def what_if(
    request: WhatIfRequest,
    service: ExplanationService = Depends(get_explanation_service),  # noqa: B008
) -> dict[str, Any]:
    try:
        result = await service.what_if(
            X_sample=request.X_sample,
            feature_changes=request.feature_changes,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("What-if analysis failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/features/{model_name}/importance",
    response_model=list[FeatureImportanceResponse],
    summary="Get global feature importance for a model",
)
async def get_feature_importance(
    model_name: str = Path(..., description="Name of the model"),
    top_n: int = Query(20, ge=1, le=100, description="Number of top features"),
    service: ExplanationService = Depends(get_explanation_service),  # noqa: B008
) -> list[dict[str, Any]]:
    try:
        importance = await service.get_feature_importance_overall(
            model_name=model_name,
            top_n=top_n,
        )
        return importance
    except Exception as exc:
        logger.error("Failed to get feature importance for %s: %s", model_name, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/compare",
    summary="Compare explanations across multiple predictions",
)
async def compare_explanations(
    request: CompareRequest,
    service: ExplanationService = Depends(get_explanation_service),  # noqa: B008
) -> dict[str, Any]:
    try:
        prediction_ids = [UUID(pid) for pid in request.prediction_ids]
        result = await service.compare_explanations(
            prediction_ids=prediction_ids,
            model_id=request.model_id,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("Explanation comparison failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/visualizations/{explanation_id}/{plot_type}",
    summary="Get visualization data for an explanation",
)
async def get_visualization(
    explanation_id: UUID = Path(..., description="UUID of the explanation"),  # noqa: B008
    plot_type: str = Path(
        ...,
        description="Type of plot: waterfall, force, bar, dependence, heatmap, summary",
    ),
    service: ExplanationService = Depends(get_explanation_service),  # noqa: B008
) -> dict[str, Any]:
    explanation = await service.get_explanation(explanation_id)
    if explanation is None:
        raise HTTPException(
            status_code=404,
            detail=f"Explanation {explanation_id} not found",
        )

    from regulaforge.xai.infrastructure.visualization import ExplanationVisualizer

    visualizer = ExplanationVisualizer()

    try:
        if plot_type == "waterfall":
            return visualizer.generate_waterfall_plot(explanation)
        elif plot_type == "force":
            return visualizer.generate_force_plot(explanation)
        elif plot_type == "bar":
            return visualizer.generate_bar_chart(explanation.features)
        elif plot_type == "dependence":
            if not explanation.features:
                raise HTTPException(status_code=422, detail="No features available for dependence plot")
            top_feature = max(explanation.features, key=lambda f: abs(f.contribution))
            shap_arr = [f.contribution for f in explanation.features]
            x_arr = [[f.feature_value if isinstance(f.feature_value, int | float) else 0.0 for f in explanation.features]]  # noqa: E501
            return visualizer.generate_dependence_plot(
                feature=top_feature.feature_name,
                shap_values=shap_arr,
                X=x_arr,
            )
        elif plot_type == "heatmap":
            return visualizer.generate_heatmap([explanation])
        elif plot_type == "summary":
            return visualizer.generate_summary_plot(explanation)
        else:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid plot type: {plot_type}. "
                       f"Valid types: waterfall, force, bar, dependence, heatmap, summary",
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to generate %s plot: %s", plot_type, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
