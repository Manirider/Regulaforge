from __future__ import annotations

from pathlib import Path
from typing import List
from uuid import uuid4

import pytest
from regulaforge.document_intelligence.application.chunking_service import ChunkingService
from regulaforge.document_intelligence.application.classification_service import ClassificationService
from regulaforge.document_intelligence.application.metadata_service import MetadataService
from regulaforge.document_intelligence.application.ner_service import NERService
from regulaforge.document_intelligence.application.ocr_service import OCRService
from regulaforge.document_intelligence.application.pipeline_service import DocumentIntelligencePipeline
from regulaforge.document_intelligence.application.relation_extraction import RelationExtractionService
from regulaforge.document_intelligence.application.table_extraction import TableExtractionService
from regulaforge.document_intelligence.domain.models import (
    BoundingBox,
    DocumentElement,
    EntityType,
    TableCell,
    TableElement,
)
from regulaforge.document_intelligence.application.models import (
    ClassificationResult,
    ConfidenceScore,
    ExtractedEntity,
    PipelineResult,
    Relation,
    SemanticMetadata,
    TextChunk,
)
from regulaforge.document_intelligence.application.enums import (
    ClassificationLabel,
    ElementType,
    RelationType,
    ProcessingStatus,
)
from regulaforge.document_intelligence.infrastructure.layout.layout_analyzer import LayoutAnalyzer
from regulaforge.document_intelligence.infrastructure.pdf.pdf_processor import PDFProcessor


@pytest.fixture
def sample_text() -> str:
    return """MASTER DIRECTION ON KYC

Reserve Bank of India
April 15, 2024

Section 1: Introduction

This Master Direction is issued by the Reserve Bank of India under Section 35A of the Banking Regulation Act, 1949.

All scheduled commercial banks shall comply with the provisions of this Direction within 90 days from the date of publication.

Section 2: Definitions

2.1 "Customer" means any person who maintains an account with the bank.
2.2 "Beneficial Owner" means the natural person who ultimately owns or controls a customer.
2.3 "PEP" means Politically Exposed Person.

Section 3: Know Your Customer Requirements

3.1 Banks shall obtain the following documents from all customers:
a) Proof of identity (Passport, Aadhaar, Voter ID)
b) Proof of address
c) Recent photograph
d) PAN card or Form 60

3.2 The customer due diligence measures shall include:
i) Identifying the customer and verifying their identity
ii) Identifying the beneficial owner
iii) Understanding the purpose of the account

Section 4: Periodic Updation

4.1 Banks shall update KYC records at least once every two years for medium risk customers.
4.2 For high risk customers, KYC shall be updated every year.

Section 5: Penalties

Any contravention of the provisions of this Direction shall attract penalty under Section 46 of the Banking Regulation Act, 1949, which may extend to Rs. 1,00,00,000 or twice the amount involved, whichever is higher.

Schedule I: List of Acceptable Documents

| Document Type | Validity Period | Remarks |
| Passport | 10 years | Valid for all purposes |
| Aadhaar | Lifetime | Subject to authentication |
| Voter ID | Lifetime | Valid for Indian citizens |
| Driving License | As per validity | Valid for non-financial purposes |
"""


@pytest.fixture
def sample_pipeline() -> DocumentIntelligencePipeline:
    return DocumentIntelligencePipeline(
        pdf_processor=PDFProcessor(),
        ocr_service=OCRService(),
        layout_analyzer=LayoutAnalyzer(),
        ner_service=NERService(),
        classification_service=ClassificationService(),
        chunking_service=ChunkingService(),
        table_extraction=TableExtractionService(),
        relation_extraction=RelationExtractionService(),
        metadata_service=MetadataService(),
    )


@pytest.fixture
def sample_elements(sample_text) -> List[DocumentElement]:
    analyzer = LayoutAnalyzer()
    import asyncio
    return asyncio.run(analyzer.analyze("", sample_text))


@pytest.fixture
def sample_entities() -> List[ExtractedEntity]:
    return [
        ExtractedEntity(
            id=uuid4(),
            entity_type=EntityType.ORGANIZATION,
            text="Reserve Bank of India",
            start_char=30,
            end_char=52,
            page=1,
            confidence=ConfidenceScore(value=0.95, model="regex"),
        ),
        ExtractedEntity(
            id=uuid4(),
            entity_type=EntityType.REGULATION,
            text="Banking Regulation Act, 1949",
            start_char=130,
            end_char=158,
            page=1,
            confidence=ConfidenceScore(value=0.9, model="regex"),
        ),
        ExtractedEntity(
            id=uuid4(),
            entity_type=EntityType.COMPLIANCE_ACTION,
            text="shall comply",
            start_char=190,
            end_char=201,
            page=1,
            confidence=ConfidenceScore(value=0.85, model="regex"),
        ),
        ExtractedEntity(
            id=uuid4(),
            entity_type=EntityType.AMOUNT,
            text="Rs. 1,00,00,000",
            start_char=800,
            end_char=814,
            page=1,
            confidence=ConfidenceScore(value=0.9, model="regex"),
        ),
    ]
