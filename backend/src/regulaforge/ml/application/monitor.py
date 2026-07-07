from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

from regulaforge.ml.domain.enums import DriftStatus
from regulaforge.ml.domain.models import DriftReport, MonitorReport

logger = logging.getLogger(__name__)


class ModelMonitor:
    def __init__(self) -> None:
        self._reports: list[MonitorReport] = []
        self._reference_data: Optional[pd.DataFrame] = None

    def set_reference_data(self, x_ref: pd.DataFrame) -> None:
        self._reference_data = x_ref.copy()
        logger.info("Reference data set with shape %s", x_ref.shape)

    def detect_drift(
        self,
        model_id: UUID,
        x_current: pd.DataFrame,
        model_version: int = 1,
        cat_columns: Optional[list[str]] = None,
        numeric_drift_threshold: float = 0.05,
        cat_drift_threshold: float = 0.05,
    ) -> MonitorReport:
        if self._reference_data is None:
            raise ValueError("Reference data not set. Call set_reference_data first.")

        cat_columns = cat_columns or []
        feature_reports: list[DriftReport] = []
        drift_count = 0

        for col in x_current.columns:
            if col not in self._reference_data.columns:
                continue

            ref_col = self._reference_data[col].dropna()
            cur_col = x_current[col].dropna()

            if col in cat_columns or ref_col.dtype == "object" or cur_col.dtype == "object":
                report = self._detect_categorical_drift(
                    col, ref_col, cur_col, cat_drift_threshold,
                )
            else:
                report = self._detect_numeric_drift(
                    col, ref_col, cur_col, numeric_drift_threshold,
                )

            feature_reports.append(report)
            if report.status in (DriftStatus.WARNING, DriftStatus.DRIFT_DETECTED):
                drift_count += 1

        n_features = len(feature_reports)
        drift_ratio = drift_count / max(n_features, 1)

        if drift_ratio > 0.3:
            overall_status = DriftStatus.DRIFT_DETECTED
        elif drift_ratio > 0.1:
            overall_status = DriftStatus.WARNING
        else:
            overall_status = DriftStatus.NO_DRIFT

        report = MonitorReport(
            model_id=model_id,
            model_version=model_version,
            overall_status=overall_status,
            feature_drift_reports=feature_reports,
            data_drift_score=drift_ratio,
            sample_size=len(x_current),
            alert_triggered=overall_status in (DriftStatus.WARNING, DriftStatus.DRIFT_DETECTED),
        )
        self._reports.append(report)
        logger.info(
            "Drift check: model=%s status=%s drift_ratio=%.3f alert=%s",
            model_id, overall_status.value, drift_ratio, report.alert_triggered,
        )
        return report

    def _detect_numeric_drift(
        self,
        col: str,
        ref: pd.Series,
        cur: pd.Series,
        _threshold: float,
    ) -> DriftReport:
        try:
            stat, p_value = sp_stats.ks_2samp(ref, cur)
        except Exception:
            stat, p_value = 0.0, 1.0

        drift_score = float(stat)
        if p_value < 0.01:
            status = DriftStatus.DRIFT_DETECTED
        elif p_value < 0.05:
            status = DriftStatus.WARNING
        else:
            status = DriftStatus.NO_DRIFT

        return DriftReport(
            feature_name=col,
            drift_score=drift_score,
            p_value=float(p_value),
            status=status,
            reference_stats={"mean": float(ref.mean()), "std": float(ref.std())},
            current_stats={"mean": float(cur.mean()), "std": float(cur.std())},
        )

    def _detect_categorical_drift(
        self,
        col: str,
        ref: pd.Series,
        cur: pd.Series,
        _threshold: float,
    ) -> DriftReport:
        ref_freq = ref.value_counts(normalize=True)
        cur_freq = cur.value_counts(normalize=True)
        all_cats = set(ref_freq.index) | set(cur_freq.index)

        psi = 0.0
        for cat in all_cats:
            p = ref_freq.get(cat, 0.0) + 1e-10
            q = cur_freq.get(cat, 0.0) + 1e-10
            psi += (p - q) * np.log(p / q)

        drift_score = float(psi)
        if drift_score > 0.25:
            status = DriftStatus.DRIFT_DETECTED
        elif drift_score > 0.1:
            status = DriftStatus.WARNING
        else:
            status = DriftStatus.NO_DRIFT

        return DriftReport(
            feature_name=col,
            drift_score=drift_score,
            p_value=1.0,
            status=status,
        )

    def get_recent_reports(self, n: int = 10) -> list[MonitorReport]:
        return self._reports[-n:]

    def get_report(self, report_id: UUID) -> Optional[MonitorReport]:
        for r in self._reports:
            if r.id == report_id:
                return r
        return None
