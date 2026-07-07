from __future__ import annotations

import pytest
from regulaforge.document_intelligence.application.classification_service import ClassificationService
from regulaforge.document_intelligence.application.enums import ClassificationLabel


class TestClassificationService:
    @pytest.fixture
    def classifier(self) -> ClassificationService:
        return ClassificationService()

    @pytest.mark.asyncio
    async def test_classify_master_direction(self, classifier, sample_text) -> None:
        result = await classifier.classify(sample_text)
        assert result.label == ClassificationLabel.LEGISLATION

    @pytest.mark.asyncio
    async def test_classify_circular(self, classifier) -> None:
        text = "CIRCULAR ON KYC COMPLIANCE\nThis circular is addressed to all banks."
        result = await classifier.classify(text)
        assert result.label == ClassificationLabel.CIRCULAR

    @pytest.mark.asyncio
    async def test_classify_notification(self, classifier) -> None:
        text = "NOTIFICATION ON CRR\nThis notification is issued."
        result = await classifier.classify(text)
        assert result.label == ClassificationLabel.NOTIFICATION

    @pytest.mark.asyncio
    async def test_classify_guideline(self, classifier) -> None:
        text = "GUIDELINES ON ASSET RECONSTRUCTION\nThese guidelines apply."
        result = await classifier.classify(text)
        assert result.label == ClassificationLabel.GUIDELINE

    @pytest.mark.asyncio
    async def test_classify_press_release(self, classifier) -> None:
        text = "PRESS RELEASE ON MONETARY POLICY\nToday the Governor announced."
        result = await classifier.classify(text)
        assert result.label == ClassificationLabel.PRESS_RELEASE

    @pytest.mark.asyncio
    async def test_classify_report(self, classifier) -> None:
        text = "ANNUAL REPORT 2024\nThis report covers."
        result = await classifier.classify(text)
        assert result.label == ClassificationLabel.REPORT

    @pytest.mark.asyncio
    async def test_classify_amendment(self, classifier) -> None:
        text = "AMENDMENT TO MASTER DIRECTION\nThe following amendments are made."
        result = await classifier.classify(text)
        assert result.label == ClassificationLabel.AMENDMENT

    @pytest.mark.asyncio
    async def test_classify_other(self, classifier) -> None:
        text = "Just some random text without any regulatory keywords."
        result = await classifier.classify(text)
        assert result.probabilities is not None
        assert len(result.probabilities) > 0

    @pytest.mark.asyncio
    async def test_probabilities_sum_to_one(self, classifier) -> None:
        text = "CIRCULAR ON KYC"
        result = await classifier.classify(text)
        total = sum(result.probabilities.values())
        assert abs(total - 1.0) < 0.01

    @pytest.mark.asyncio
    async def test_classify_policy(self, classifier) -> None:
        text = "POLICY ON DATA PROTECTION\nThis policy applies to all data processing."
        result = await classifier.classify(text)
        assert result.label == ClassificationLabel.POLICY
