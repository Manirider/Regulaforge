"""
Semantic document chunking strategies.

Splits document text into semantically meaningful chunks using embedding
similarity, sentence boundaries, and structural markers.
"""

from regulaforge.document_intelligence.chunking.semantic_chunker import (
    ChunkOverlapMode,
    SemanticChunker,
    SemanticChunkingResult,
)

__all__ = [
    "ChunkOverlapMode",
    "SemanticChunker",
    "SemanticChunkingResult",
]
