"""Tests for evaluation metrics."""

from __future__ import annotations

import pytest

from regulaforge.document_intelligence.domain.enums import ClauseType, EntityType
from regulaforge.document_intelligence.domain.models import ExtractedEntity, IdentifiedClause, SemanticChunk
from regulaforge.document_intelligence.evaluation.metrics import (
    Annotation,
    evaluate_chunking,
    evaluate_clauses,
    evaluate_entities,
)


def test_evaluate_entities_perfect():
    preds = [
        ExtractedEntity(type=EntityType.ORGANIZATION, text="RBI", confidence=0.9),
        ExtractedEntity(type=EntityType.DATE, text="2024", confidence=0.9),
    ]
    gts = [
        Annotation(text="RBI", type="organization"),
        Annotation(text="2024", type="date"),
    ]
    metrics = evaluate_entities(preds, gts)
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.f1 == 1.0


def test_evaluate_entities_no_match():
    preds = [
        ExtractedEntity(type=EntityType.ORGANIZATION, text="SEBI", confidence=0.9),
    ]
    gts = [
        Annotation(text="RBI", type="organization"),
    ]
    metrics = evaluate_entities(preds, gts)
    assert metrics.precision == 0.0
    assert metrics.recall == 0.0
    assert metrics.f1 == 0.0


def test_evaluate_entities_partial():
    preds = [
        ExtractedEntity(type=EntityType.ORGANIZATION, text="RBI", confidence=0.9),
        ExtractedEntity(type=EntityType.DATE, text="2025", confidence=0.8),
    ]
    gts = [
        Annotation(text="RBI", type="organization"),
        Annotation(text="2024", type="date"),
    ]
    metrics = evaluate_entities(preds, gts)
    assert metrics.true_positives == 1  # only RBI matches
    assert metrics.false_positives == 1  # 2025 has no match
    assert metrics.false_negatives == 1  # 2024 not found


def test_evaluate_entities_case_insensitive():
    preds = [
        ExtractedEntity(type=EntityType.ORGANIZATION, text="rbi", confidence=0.9),
    ]
    gts = [
        Annotation(text="RBI", type="organization"),
    ]
    metrics = evaluate_entities(preds, gts)
    assert metrics.f1 == 1.0


def test_evaluate_entities_type_filter():
    preds = [
        ExtractedEntity(type=EntityType.ORGANIZATION, text="RBI", confidence=0.9),
        ExtractedEntity(type=EntityType.DATE, text="2024", confidence=0.9),
    ]
    gts = [
        Annotation(text="RBI", type="organization"),
        Annotation(text="2024", type="date"),
    ]
    metrics = evaluate_entities(preds, gts, type_filter="organization")
    assert metrics.true_positives == 1
    assert metrics.false_negatives == 0  # date filtered out of both sets


def test_evaluate_entities_empty():
    metrics = evaluate_entities([], [])
    assert metrics.f1 == 0.0


def test_evaluate_clauses_perfect():
    preds = [
        IdentifiedClause(clause_type=ClauseType.OBLIGATION, text="shall comply", confidence=0.9),
    ]
    gts = [
        Annotation(text="shall comply", type="obligation"),
    ]
    metrics = evaluate_clauses(preds, gts)
    assert metrics.f1 == 1.0


def test_evaluate_clauses_no_match():
    preds = [
        IdentifiedClause(clause_type=ClauseType.OBLIGATION, text="shall comply", confidence=0.9),
    ]
    gts = [
        Annotation(text="shall report", type="reporting"),
    ]
    metrics = evaluate_clauses(preds, gts)
    assert metrics.f1 == 0.0


def test_evaluate_clauses_empty():
    metrics = evaluate_clauses([], [])
    assert metrics.f1 == 0.0


def test_evaluate_chunking_empty():
    metrics = evaluate_chunking([], [])
    assert metrics.boundary_f1 == 0.0


def test_evaluate_chunking_no_boundary_metadata():
    chunks = [
        SemanticChunk(text="some text", metadata={}),
    ]
    metrics = evaluate_chunking(chunks, [{"start": 0, "end": 100}])
    assert metrics.boundary_precision == 0.0
