from __future__ import annotations

from uuid import uuid4

import pandas as pd
import pytest
from regulaforge.ml.application.retrainer import Retrainer
from regulaforge.ml.domain.enums import ModelType, TaskType


class TestRetrainer:
    @pytest.fixture
    def retrainer(self):
        return Retrainer()

    def test_create_retraining_job(self, retrainer):
        model_id = uuid4()
        job = retrainer.create_retraining_job(model_id, "test_trigger")
        assert job.model_id == model_id
        assert job.trigger_reason == "test_trigger"
        assert job.status == "pending"

    def test_execute_retraining_success(self, retrainer):
        model_id = uuid4()
        job = retrainer.create_retraining_job(model_id, "scheduled")
        X = pd.DataFrame({"a": [1, 2, 3, 4, 5, 6], "b": [2, 3, 4, 5, 6, 7]})
        y = pd.Series([0, 0, 1, 1, 0, 1])
        completed = retrainer.execute_retraining(
            job.id, X, y,
            model_type=ModelType.XGBOOST,
            task_type=TaskType.RISK_CLASSIFICATION,
            current_model_metrics={"f1": 0.8},
        )
        assert completed.status == "completed"
        assert completed.new_model_id is not None
        assert completed.metrics_before == {"f1": 0.8}
        assert completed.metrics_after is not None
        assert "f1" in completed.metrics_after

    def test_execute_retraining_job_not_found(self, retrainer):
        X = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        y = pd.Series([0, 1])
        with pytest.raises(ValueError, match="not found"):
            retrainer.execute_retraining(
                uuid4(), X, y,
                model_type=ModelType.XGBOOST,
                task_type=TaskType.RISK_CLASSIFICATION,
            )

    def test_get_job(self, retrainer):
        model_id = uuid4()
        job = retrainer.create_retraining_job(model_id)
        assert retrainer.get_job(job.id) is job

    def test_get_job_not_found(self, retrainer):
        assert retrainer.get_job(uuid4()) is None

    def test_list_jobs(self, retrainer):
        model_id = uuid4()
        retrainer.create_retraining_job(model_id, "scheduled")
        retrainer.create_retraining_job(model_id, "drift")
        assert len(retrainer.list_jobs()) == 2

    def test_list_jobs_by_status(self, retrainer):
        model_id = uuid4()
        retrainer.create_retraining_job(model_id, "scheduled")
        assert len(retrainer.list_jobs("pending")) == 1
        assert len(retrainer.list_jobs("completed")) == 0
