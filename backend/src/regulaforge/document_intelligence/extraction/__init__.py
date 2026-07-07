"""
Information extraction components: NER, relation extraction, clause detection,
and metadata extraction.
"""

from regulaforge.document_intelligence.extraction.ner import NerEngine, NerResult
from regulaforge.document_intelligence.extraction.relations import RelationExtractor, RelationResult
from regulaforge.document_intelligence.extraction.clauses import ClauseDetector, ClauseResult
from regulaforge.document_intelligence.extraction.metadata import MetadataExtractor, MetadataResult

__all__ = [
    "NerEngine",
    "NerResult",
    "RelationExtractor",
    "RelationResult",
    "ClauseDetector",
    "ClauseResult",
    "MetadataExtractor",
    "MetadataResult",
]
