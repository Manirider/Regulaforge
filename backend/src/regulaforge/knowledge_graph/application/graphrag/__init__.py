"""GraphRAG engine — enterprise retrieval-augmented generation over the knowledge graph.

Provides hybrid dense/sparse retrieval, cross-encoder reranking, context
compression, grounding with source attribution and citations, confidence
scoring, evaluation metrics, and latency benchmarking. All components are
production-ready with full logging, error handling, and async support.
"""

from regulaforge.knowledge_graph.application.graphrag.engine import GraphRAGEngine

__all__ = [
    "GraphRAGEngine",
]
