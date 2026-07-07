from enum import Enum


class GraphNodeLabel(str, Enum):
    DOCUMENT = "Document"
    CHUNK = "Chunk"
    ENTITY = "Entity"
    CONCEPT = "Concept"
    TEMPORAL_EVENT = "TemporalEvent"
    SOURCE = "Source"


class GraphRelationshipType(str, Enum):
    CONTAINS = "CONTAINS"
    HAS_ENTITY = "HAS_ENTITY"
    MENTIONS = "MENTIONS"
    RELATED_TO = "RELATED_TO"
    DEPENDS_ON = "DEPENDS_ON"
    REFERENCES = "REFERENCES"
    TEMPORAL_AFTER = "TEMPORAL_AFTER"
    TEMPORAL_BEFORE = "TEMPORAL_BEFORE"
    TEMPORAL_DURING = "TEMPORAL_DURING"
    CO_OCCURS_WITH = "CO_OCCURS_WITH"
    IS_A = "IS_A"
    PART_OF = "PART_OF"
    CAUSES = "CAUSES"
    REGULATES = "REGULATES"
    AMENDS = "AMENDS"
    SUPERSEDES = "SUPERSEDES"


class EntityCategory(str, Enum):
    ORGANIZATION = "ORGANIZATION"
    PERSON = "PERSON"
    REGULATION = "REGULATION"
    STATUTE = "STATUTE"
    JURISDICTION = "JURISDICTION"
    DATE = "DATE"
    AMOUNT = "AMOUNT"
    PENALTY = "PENALTY"
    COMPLIANCE_REQUIREMENT = "COMPLIANCE_REQUIREMENT"
    REPORTING_DEADLINE = "REPORTING_DEADLINE"
    DEFINITION = "DEFINITION"
    CITATION = "CITATION"


class TemporalRelation(str, Enum):
    AFTER = "AFTER"
    BEFORE = "BEFORE"
    DURING = "DURING"
    OVERLAPS = "OVERLAPS"
    STARTS = "STARTS"
    FINISHES = "FINISHES"
    EQUALS = "EQUALS"


class RetrievalStrategy(str, Enum):
    VECTOR_ONLY = "vector_only"
    BM25_ONLY = "bm25_only"
    GRAPH_ONLY = "graph_only"
    HYBRID_VECTOR_BM25 = "hybrid_vector_bm25"
    HYBRID_VECTOR_GRAPH = "hybrid_vector_graph"
    HYBRID_FULL = "hybrid_full"
    TEMPORAL = "temporal"
