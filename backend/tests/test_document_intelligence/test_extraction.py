"""Tests for extraction engines (NER, relations, clauses, metadata)."""

from __future__ import annotations

from pathlib import Path

import pytest

from regulaforge.document_intelligence.domain.enums import ClauseType, EntityType
from regulaforge.document_intelligence.domain.models import ExtractedEntity
from regulaforge.document_intelligence.extraction.clauses import RegexClauseDetector
from regulaforge.document_intelligence.extraction.ner import (
    FINANCIAL_ENTITY_KEYWORDS,
    HuggingFaceNerEngine,
    SpacyNerEngine,
)
from regulaforge.document_intelligence.extraction.relations import RuleBasedRelationExtractor


def test_financial_keywords_defined():
    assert len(FINANCIAL_ENTITY_KEYWORDS) > 0
    assert EntityType.REGULATION_ID in FINANCIAL_ENTITY_KEYWORDS


@pytest.mark.asyncio
async def test_spacy_ner_not_available():
    engine = SpacyNerEngine()
    # spacy shouldn't be installed in test env
    available = await engine.is_available()
    assert isinstance(available, bool)


@pytest.mark.asyncio
async def test_hf_ner_not_available():
    engine = HuggingFaceNerEngine()
    available = await engine.is_available()
    assert isinstance(available, bool)


def test_rule_based_relation_extractor_always_available():
    ext = RuleBasedRelationExtractor()
    assert ext.name == "rule-based"


@pytest.mark.asyncio
async def test_rule_based_relation_extractor_empty():
    ext = RuleBasedRelationExtractor()
    result = await ext.extract([], "")
    assert result.relations == []
    assert result.overall_confidence == 0.0


@pytest.mark.asyncio
async def test_rule_based_relation_extractor_finds_relations():
    ext = RuleBasedRelationExtractor(max_distance=500)
    entities = [
        ExtractedEntity(
            id="ent-1", type=EntityType.REGULATION_ID,
            text="Circular 2024/01", confidence=0.9,
            metadata={"start": 0},
        ),
        ExtractedEntity(
            id="ent-2", type=EntityType.SECTION_NUMBER,
            text="Section 4A", confidence=0.85,
            metadata={"start": 100},
        ),
    ]
    result = await ext.extract(entities, "Circular 2024/01 refers to Section 4A")
    assert len(result.relations) >= 1
    assert result.relations[0].source_id == "ent-1"
    assert result.relations[0].target_id == "ent-2"


@pytest.mark.asyncio
async def test_rule_based_relation_out_of_distance():
    ext = RuleBasedRelationExtractor(max_distance=10)
    entities = [
        ExtractedEntity(
            id="ent-1", type=EntityType.REGULATION_ID,
            text="Circular 2024/01", confidence=0.9,
            metadata={"start": 0},
        ),
        ExtractedEntity(
            id="ent-2", type=EntityType.SECTION_NUMBER,
            text="Section 4A", confidence=0.85,
            metadata={"start": 100},
        ),
    ]
    result = await ext.extract(entities, "x" * 200)
    assert len(result.relations) == 0


@pytest.mark.asyncio
async def test_regex_clause_detector_available():
    d = RegexClauseDetector()
    assert await d.is_available()
    assert d.name == "regex"


@pytest.mark.asyncio
async def test_regex_clause_detector_empty():
    d = RegexClauseDetector()
    result = await d.detect("")
    assert result.clauses == []


@pytest.mark.asyncio
async def test_regex_clause_detector_finds_obligation():
    d = RegexClauseDetector()
    text = "The bank shall ensure compliance with all regulations."
    result = await d.detect(text)
    obligations = [c for c in result.clauses if c.clause_type == ClauseType.OBLIGATION]
    assert len(obligations) >= 1
    assert "shall ensure" in obligations[0].text.lower()


@pytest.mark.asyncio
async def test_regex_clause_detector_finds_penalty():
    d = RegexClauseDetector()
    text = "Any violation shall be liable to penalty of up to ₹1 crore."
    result = await d.detect(text)
    penalties = [c for c in result.clauses if c.clause_type == ClauseType.PENALTY]
    assert len(penalties) >= 1


@pytest.mark.asyncio
async def test_regex_clause_detector_with_headings():
    d = RegexClauseDetector()
    text = (
        "Definitions and Interpretation\n"
        "In this Regulation, unless the context otherwise requires...\n"
        "Penalties\n"
        "Any violation shall be punishable with fine."
    )
    boundaries = [(0, 60, "Definitions and Interpretation"), (65, 130, "Penalties")]
    result = await d.detect(text, section_boundaries=boundaries)
    types = {c.clause_type for c in result.clauses}
    assert ClauseType.DEFINITION in types
    assert ClauseType.PENALTY in types


@pytest.mark.asyncio
async def test_regex_clause_detector_no_duplicates():
    d = RegexClauseDetector()
    text = "The bank shall ensure compliance. The bank shall ensure compliance."
    result = await d.detect(text)
    clauses = [c for c in result.clauses if "shall ensure" in c.text]
    if len(clauses) > 1:
        texts = [c.text for c in clauses]
        assert len(set(texts)) == len(texts), "duplicate clause texts found"


def test_clause_patterns_have_all_required_types():
    from regulaforge.document_intelligence.extraction.clauses import CLAUSE_PATTERNS
    required = [
        ClauseType.DEFINITION, ClauseType.OBLIGATION, ClauseType.PROHIBITION,
        ClauseType.PENALTY, ClauseType.COMPLIANCE, ClauseType.REPORTING,
        ClauseType.EFFECTIVE_DATE, ClauseType.AMENDMENT, ClauseType.REPEAL,
        ClauseType.SAVINGS,
    ]
    for ct in required:
        assert ct in CLAUSE_PATTERNS, f"missing patterns for {ct}"
