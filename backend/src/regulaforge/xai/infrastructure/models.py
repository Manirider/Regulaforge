"""SQLAlchemy ORM models for the XAI subsystem.

Stores generated explanations, feature contributions, and
counterfactual data in a relational format with JSON columns
for flexible schema evolution.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON as SA_JSON
from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from regulaforge.infrastructure.persistence.database import Base
from regulaforge.infrastructure.persistence.models.base import GUID, TimestampMixin


class ExplanationModel(TimestampMixin, Base):
    """ORM model for storing AI model explanations.

    Persists explanation data including feature contributions,
    metadata, and serialized visualization data. Each row represents
    a single explanation generated for a prediction.
    """

    __tablename__ = "explanations"

    id: Mapped[GUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid4,
        comment="Unique explanation identifier",
    )
    prediction_id: Mapped[GUID] = mapped_column(
        GUID,
        nullable=False,
        index=True,
        comment="Reference to the prediction being explained",
    )
    model_name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
        comment="Name of the model that was explained",
    )
    explanation_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
        comment="Type of explanation (shap, lime, counterfactual, etc.)",
    )
    features: Mapped[dict] = mapped_column(
        SA_JSON,
        nullable=True,
        default=list,
        comment="List of feature contributions with SHAP/LIME values",
    )
    summary: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable summary of the explanation",
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        comment="Confidence score for this explanation (0.0-1.0)",
    )
    visualization_data: Mapped[dict] = mapped_column(
        SA_JSON,
        nullable=True,
        default=dict,
        comment="Serialized data for rendering visualizations",
    )
    natural_language: Mapped[dict] = mapped_column(
        SA_JSON,
        nullable=True,
        default=dict,
        comment="Natural language explanation data",
    )
    metadata_json: Mapped[dict] = mapped_column(
        SA_JSON,
        nullable=True,
        default=dict,
        comment="Additional metadata (model version, parameters, etc.)",
    )
    explanation_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        comment="When the explanation was generated (UTC)",
    )

    def __repr__(self) -> str:
        return (
            f"<ExplanationModel id={self.id} "
            f"prediction={self.prediction_id} "
            f"type={self.explanation_type} "
            f"model={self.model_name}>"
        )


class CounterfactualModel(TimestampMixin, Base):
    """ORM model for storing counterfactual explanations."""

    __tablename__ = "counterfactual_explanations"

    id: Mapped[GUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid4,
        comment="Unique counterfactual identifier",
    )
    prediction_id: Mapped[GUID] = mapped_column(
        GUID,
        nullable=False,
        index=True,
        comment="Reference to the original prediction",
    )
    original_input: Mapped[dict] = mapped_column(
        SA_JSON,
        nullable=False,
        comment="Original input feature values",
    )
    counterfactual_input: Mapped[dict] = mapped_column(
        SA_JSON,
        nullable=False,
        comment="Counterfactual input feature values",
    )
    feature_changes: Mapped[dict] = mapped_column(
        SA_JSON,
        nullable=True,
        default=list,
        comment="List of feature changes between original and counterfactual",
    )
    outcome_change: Mapped[str] = mapped_column(
        String(256),
        nullable=True,
        comment="Description of how the outcome would change",
    )
    distance: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="Distance between original and counterfactual",
    )
    viability: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="Feasibility score for the counterfactual (0.0-1.0)",
    )
    natural_language: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable description of the counterfactual",
    )

    def __repr__(self) -> str:
        return (
            f"<CounterfactualModel id={self.id} "
            f"prediction={self.prediction_id} "
            f"distance={self.distance:.3f}>"
        )
