from __future__ import annotations

from uuid import uuid4

import pandas as pd
import pytest
from regulaforge.ml.application.monitor import ModelMonitor
from regulaforge.ml.domain.enums import DriftStatus


class TestModelMonitor:
    @pytest.fixture
    def monitor(self):
        m = ModelMonitor()
        m.set_reference_data(pd.DataFrame({
            "num_feat": [1.0, 2.0, 3.0, 4.0, 5.0],
            "cat_feat": ["a", "b", "a", "b", "c"],
        }))
        return m

    def test_detect_drift_no_drift(self, monitor):
        model_id = uuid4()
        X_cur = pd.DataFrame({
            "num_feat": [1.1, 2.1, 3.1, 4.1, 5.1],
            "cat_feat": ["a", "b", "c", "a", "b"],
        })
        report = monitor.detect_drift(model_id, X_cur)
        assert report.model_id == model_id
        assert report.overall_status in (DriftStatus.NO_DRIFT, DriftStatus.WARNING)

    def test_detect_drift_drifted(self, monitor):
        model_id = uuid4()
        X_cur = pd.DataFrame({
            "num_feat": [100.0, 200.0, 300.0, 400.0, 500.0],
            "cat_feat": ["x"] * 5,
        })
        report = monitor.detect_drift(model_id, X_cur)
        assert report.alert_triggered

    def test_drift_without_reference_raises(self):
        monitor = ModelMonitor()
        with pytest.raises(ValueError, match="Reference data not set"):
            monitor.detect_drift(uuid4(), pd.DataFrame({"a": [1]}))

    def test_detect_numeric_drift(self, monitor):
        model_id = uuid4()
        X_cur = pd.DataFrame({
            "num_feat": [1.0, 2.0, 3.0, 4.0, 5.0],
            "cat_feat": ["a", "b", "a", "b", "c"],
        })
        report = monitor.detect_drift(model_id, X_cur)
        for dr in report.feature_drift_reports:
            if dr.feature_name == "num_feat":
                assert dr.drift_score >= 0
                assert dr.p_value > 0

    def test_alert_triggered_on_drift(self, monitor):
        model_id = uuid4()
        X_cur = pd.DataFrame({
            "num_feat": [100.0, 200.0, 300.0, 400.0, 500.0],
            "cat_feat": ["x", "y", "x", "y", "z"],
        })
        report = monitor.detect_drift(model_id, X_cur)
        if report.overall_status in (DriftStatus.WARNING, DriftStatus.DRIFT_DETECTED):
            assert report.alert_triggered

    def test_get_recent_reports(self, monitor):
        model_id = uuid4()
        X_cur = pd.DataFrame({
            "num_feat": [1.0, 2.0, 3.0, 4.0, 5.0],
            "cat_feat": ["a", "b", "a", "b", "c"],
        })
        monitor.detect_drift(model_id, X_cur)
        assert len(monitor.get_recent_reports()) == 1

    def test_get_report_by_id(self, monitor):
        model_id = uuid4()
        X_cur = pd.DataFrame({
            "num_feat": [1.0, 2.0, 3.0, 4.0, 5.0],
            "cat_feat": ["a", "b", "a", "b", "c"],
        })
        report = monitor.detect_drift(model_id, X_cur)
        assert monitor.get_report(report.id) is report

    def test_get_report_not_found(self, monitor):
        from uuid import uuid4
        assert monitor.get_report(uuid4()) is None

    def test_categorical_drift_detection(self, monitor):
        model_id = uuid4()
        X_cur = pd.DataFrame({
            "num_feat": [1.0, 2.0, 3.0, 4.0, 5.0],
            "cat_feat": ["x", "y", "z", "w", "v"],
        })
        report = monitor.detect_drift(model_id, X_cur, cat_columns=["cat_feat"])
        cat_reports = [r for r in report.feature_drift_reports if r.feature_name == "cat_feat"]
        assert len(cat_reports) == 1
        assert cat_reports[0].drift_score > 0
