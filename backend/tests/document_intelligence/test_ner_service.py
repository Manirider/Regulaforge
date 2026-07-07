from __future__ import annotations

import pytest
from regulaforge.document_intelligence.application.ner_service import NERService
from regulaforge.document_intelligence.domain.models import EntityType


class TestNERService:
    @pytest.fixture
    def ner_service(self) -> NERService:
        return NERService()

    @pytest.mark.asyncio
    async def test_extract_organization(self, ner_service) -> None:
        text = "The Reserve Bank of India issued this circular."
        entities = await ner_service.extract(text)
        orgs = [e for e in entities if e.entity_type == EntityType.ORGANIZATION]
        assert len(orgs) >= 1
        assert "Reserve Bank of India" in orgs[0].text

    @pytest.mark.asyncio
    async def test_extract_section(self, ner_service) -> None:
        text = "As per Section 35A of the Act."
        entities = await ner_service.extract(text)
        sections = [e for e in entities if e.entity_type == EntityType.SECTION]
        assert len(sections) >= 1
        assert "Section 35A" in sections[0].text

    @pytest.mark.asyncio
    async def test_extract_amount(self, ner_service) -> None:
        text = "Penalty of Rs. 5,00,000 shall be imposed."
        entities = await ner_service.extract(text)
        amounts = [e for e in entities if e.entity_type == EntityType.AMOUNT]
        assert len(amounts) >= 1

    @pytest.mark.asyncio
    async def test_extract_percentage(self, ner_service) -> None:
        text = "The rate shall not exceed 12.5 percent per annum."
        entities = await ner_service.extract(text)
        pcts = [e for e in entities if e.entity_type == EntityType.PERCENTAGE]
        assert len(pcts) >= 1

    @pytest.mark.asyncio
    async def test_extract_penalty(self, ner_service) -> None:
        text = "Any contravention shall attract penalty of Rs. 1,00,000."
        entities = await ner_service.extract(text)
        penalties = [e for e in entities if e.entity_type == EntityType.PENALTY]
        assert len(penalties) >= 1

    @pytest.mark.asyncio
    async def test_extract_jurisdiction(self, ner_service) -> None:
        text = "This applies to all banks in India."
        entities = await ner_service.extract(text)
        jurisdictions = [e for e in entities if e.entity_type == EntityType.JURISDICTION]
        assert len(jurisdictions) >= 1

    @pytest.mark.asyncio
    async def test_extract_compliance_action(self, ner_service) -> None:
        text = "Banks shall comply with these requirements."
        entities = await ner_service.extract(text)
        actions = [e for e in entities if e.entity_type == EntityType.COMPLIANCE_ACTION]
        assert len(actions) >= 1

    @pytest.mark.asyncio
    async def test_no_duplicates(self, ner_service) -> None:
        text = "RBI RBI RBI"
        entities = await ner_service.extract(text)
        rbis = [e for e in entities if "RBI" in e.text]
        assert len(rbis) <= 1

    @pytest.mark.asyncio
    async def test_normalize_amount(self, ner_service) -> None:
        text = "Amount of Rs. 1,50,00,000"
        entities = await ner_service.extract(text)
        for e in entities:
            if e.entity_type == EntityType.AMOUNT:
                assert e.normalized_value is not None
                break

    @pytest.mark.asyncio
    async def test_empty_text(self, ner_service) -> None:
        entities = await ner_service.extract("")
        assert entities == []

    @pytest.mark.asyncio
    async def test_full_regulatory_text(self, ner_service, sample_text) -> None:
        entities = await ner_service.extract(sample_text)
        assert len(entities) >= 3
        types_found = {e.entity_type for e in entities}
        assert EntityType.ORGANIZATION in types_found
        assert EntityType.COMPLIANCE_ACTION in types_found
        assert EntityType.AMOUNT in types_found

    @pytest.mark.asyncio
    async def test_extract_date(self, ner_service) -> None:
        text = "This direction is issued on 15th April 2024."
        entities = await ner_service.extract(text)
        dates = [e for e in entities if e.entity_type == EntityType.DATE]
        assert len(dates) >= 1
