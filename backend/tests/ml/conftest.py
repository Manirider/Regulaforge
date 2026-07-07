from __future__ import annotations

from typing import Any

import pandas as pd
import pytest
from regulaforge.ml.domain.enums import ModelType, TaskType
from regulaforge.ml.domain.models import FeatureSet


@pytest.fixture
def sample_data() -> dict[str, Any]:
    return {
        "X_train": pd.DataFrame({
            "feature_1": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
            "feature_2": [2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0],
            "feature_3": [0, 0, 1, 1, 0, 0, 1, 1],
        }),
        "y_train": pd.Series([0, 0, 1, 1, 0, 0, 1, 1]),
        "X_test": pd.DataFrame({
            "feature_1": [1.5, 2.5],
            "feature_2": [3.5, 4.5],
            "feature_3": [0, 1],
        }),
        "y_test": pd.Series([0, 1]),
    }


@pytest.fixture
def risk_data() -> dict[str, Any]:
    return {
        "X_train": pd.DataFrame({
            "amount": [1000, 50000, 200, 100000],
            "threshold": [5000, 10000, 5000, 10000],
            "past_due_days": [0, 30, 0, 90],
            "credit_score": [750, 620, 800, 580],
            "transaction_count": [10, 50, 5, 200],
            "has_collateral": [1, 0, 1, 0],
            "industry_code": ["finance", "tech", "health", "finance"],
            "region": ["north", "south", "north", "east"],
        }),
        "y_train": pd.Series([0, 1, 0, 1]),
        "X_test": pd.DataFrame({
            "amount": [2000, 75000],
            "threshold": [5000, 10000],
            "past_due_days": [5, 60],
            "credit_score": [700, 600],
            "transaction_count": [20, 100],
            "has_collateral": [1, 0],
            "industry_code": ["tech", "finance"],
            "region": ["west", "south"],
        }),
        "y_test": pd.Series([0, 1]),
    }


@pytest.fixture
def compliance_data() -> dict[str, Any]:
    return {
        "X_train": pd.DataFrame({
            "regulation_count": [5, 20, 3, 15],
            "days_since_last_review": [30, 200, 10, 365],
            "past_violations": [0, 3, 0, 1],
            "filing_delay_days": [0, 15, 0, 5],
            "audit_score": [95, 65, 90, 75],
            "entity_size": ["small", "large", "small", "medium"],
            "sector": ["finance", "banking", "insurance", "finance"],
            "jurisdiction": ["rbi", "sebi", "irdai", "rbi"],
        }),
        "y_train": pd.Series([1, 0, 1, 1]),
        "X_test": pd.DataFrame({
            "regulation_count": [8, 25],
            "days_since_last_review": [60, 300],
            "past_violations": [0, 5],
            "filing_delay_days": [2, 30],
            "audit_score": [88, 55],
            "entity_size": ["medium", "large"],
            "sector": ["insurance", "banking"],
            "jurisdiction": ["irdai", "sebi"],
        }),
        "y_test": pd.Series([1, 0]),
    }
