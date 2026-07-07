"""Cypher query templates for Neo4j graph operations.

All queries are parameterized and designed for the RegulaForge
knowledge graph schema with temporal versioning support.
"""


# ---------------------------------------------------------------------------
# Node Creation
# ---------------------------------------------------------------------------

CREATE_REGULATION_NODE: str = """
CREATE (n:REGULATION {
    id: $id,
    node_type: $node_type,
    labels: $labels,
    title: $title,
    code: $code,
    description: $description,
    issuing_body: $issuing_body,
    jurisdiction: $jurisdiction,
    category: $category,
    status: $status,
    effective_date: $effective_date,
    version_str: $version_str,
    tags: $tags,
    valid_from: datetime($valid_from),
    valid_to: $valid_to,
    version: $version,
    created_at: datetime($created_at),
    updated_at: datetime($updated_at),
    embedding: $embedding
})
RETURN n
"""

CREATE_CLAUSE_NODE: str = """
CREATE (n:CLAUSE {
    id: $id,
    node_type: $node_type,
    labels: $labels,
    clause_id: $clause_id,
    title: $title,
    text: $text,
    section: $section,
    obligation_summary: $obligation_summary,
    valid_from: datetime($valid_from),
    valid_to: $valid_to,
    version: $version,
    created_at: datetime($created_at),
    updated_at: datetime($updated_at),
    embedding: $embedding
})
RETURN n
"""

CREATE_OBLIGATION_NODE: str = """
CREATE (n:OBLIGATION {
    id: $id,
    node_type: $node_type,
    labels: $labels,
    title: $title,
    text: $text,
    regulation_code: $regulation_code,
    clause_ref: $clause_ref,
    is_mandatory: $is_mandatory,
    risk_weight: $risk_weight,
    compliance_deadline: $compliance_deadline,
    valid_from: datetime($valid_from),
    valid_to: $valid_to,
    version: $version,
    created_at: datetime($created_at),
    updated_at: datetime($updated_at),
    embedding: $embedding
})
RETURN n
"""

# ---------------------------------------------------------------------------
# Relationship Creation
# ---------------------------------------------------------------------------

CREATE_RELATIONSHIP: str = """
MATCH (source {id: $source_id})
MATCH (target {id: $target_id})
CREATE (source)-[r:RELATIONSHIP {
    id: $id,
    rel_type: $rel_type,
    properties: $properties,
    valid_from: datetime($valid_from),
    valid_to: $valid_to,
    version: $version,
    created_at: datetime($created_at),
    updated_at: datetime($updated_at)
}]->(target)
RETURN r
"""

# ---------------------------------------------------------------------------
# Path Finding
# ---------------------------------------------------------------------------

FIND_PATH: str = """
MATCH path = shortestPath(
    (source {id: $source_id})-[*..$max_depth]-(target {id: $target_id})
)
WHERE ALL(r IN relationships(path) WHERE
    (r.valid_from IS NULL OR r.valid_from <= datetime($as_of))
    AND (r.valid_to IS NULL OR r.valid_to > datetime($as_of))
)
RETURN [n IN nodes(path) | n {.id, .node_type, .title, .code}] AS nodes,
       [r IN relationships(path) | r {.id, .rel_type, .source_id, .target_id}] AS relationships,
       length(path) AS depth
"""

# ---------------------------------------------------------------------------
# Neighborhood
# ---------------------------------------------------------------------------

FIND_NEIGHBORHOOD: str = """
MATCH (center {id: $node_id})
OPTIONAL MATCH (center)-[r*1..$depth]-(neighbor)
WHERE ALL(rel IN r WHERE
    (rel.valid_from IS NULL OR rel.valid_from <= datetime($as_of))
    AND (rel.valid_to IS NULL OR rel.valid_to > datetime($as_of))
)
RETURN collect(DISTINCT center {.id, .node_type, .title, .code, .labels}) AS center_nodes,
       collect(DISTINCT neighbor {.id, .node_type, .title, .code, .labels}) AS neighbor_nodes,
       [rel IN r | rel {.id, .rel_type, .properties, .source_id, .target_id, .valid_from, .valid_to}] AS relationships
"""

# ---------------------------------------------------------------------------
# Hybrid Search (Vector + Text)
# ---------------------------------------------------------------------------

HYBRID_SEARCH_INDEX_VECTOR: str = "regulaforge_node_embeddings"
HYBRID_SEARCH_INDEX_FULLTEXT: str = "regulaforge_node_fulltext"

HYBRID_SEARCH: str = f"""
CALL {{
    CALL db.index.vector.queryNodes('{HYBRID_SEARCH_INDEX_VECTOR}', $top_k * 2, $embedding)
    YIELD node AS vector_node, score AS vector_score
    RETURN vector_node, vector_score
    UNION
    CALL db.index.fulltext.queryNodes('{HYBRID_SEARCH_INDEX_FULLTEXT}', $query_text)
    YIELD node AS text_node, score AS text_score
    RETURN text_node, text_score
}}
WITH vector_node, vector_score, text_node, text_score
WITH
    CASE WHEN vector_node IS NOT NULL THEN vector_node ELSE text_node END AS node,
    CASE
        WHEN vector_score IS NOT NULL AND text_score IS NOT NULL THEN
            0.7 * vector_score + 0.3 * text_score
        WHEN vector_score IS NOT NULL THEN vector_score
        ELSE text_score
    END AS combined_score
WHERE ($filters IS NULL
    OR node.node_type IN $filters.node_type
    OR ALL(label IN $filters.labels WHERE label IN node.labels))
RETURN DISTINCT node.id AS id,
       node.node_type AS node_type,
       node.title AS title,
       node.code AS code,
       node.labels AS labels,
       node.embedding AS embedding,
       combined_score AS score
ORDER BY combined_score DESC
LIMIT $top_k
"""

# ---------------------------------------------------------------------------
# Temporal Queries
# ---------------------------------------------------------------------------

GET_TEMPORAL_SNAPSHOT: str = """
MATCH (n {id: $node_id})
WHERE n.valid_from <= datetime($as_of)
  AND (n.valid_to IS NULL OR n.valid_to > datetime($as_of))
RETURN n
ORDER BY n.version DESC
LIMIT 1
"""

GET_TEMPORAL_HISTORY: str = """
MATCH (n {id: $node_id})
RETURN n
ORDER BY n.valid_from ASC
"""

# ---------------------------------------------------------------------------
# Impact Analysis
# ---------------------------------------------------------------------------

GET_IMPACT_ANALYSIS: str = """
MATCH (reg:REGULATION {id: $regulation_id})
OPTIONAL MATCH (reg)-[:DERIVES_FROM]->(clause:CLAUSE)
OPTIONAL MATCH (reg)-[:APPLIES_TO]->(entity:ENTITY)
OPTIONAL MATCH (reg)-[:CREATES_OBLIGATION]->(obl:OBLIGATION)
OPTIONAL MATCH (reg)-[:REFERENCES]->(risk:RISK_FACTOR)
RETURN collect(DISTINCT entity {.id, .name, .entity_type}) AS entities,
       collect(DISTINCT clause {.id, .clause_id, .title, .section}) AS clauses,
       collect(DISTINCT obl {.id, .title, .text, .risk_weight}) AS obligations,
       collect(DISTINCT risk {.id, .title, .risk_level}) AS risk_factors
"""

FIND_AFFECTED_ENTITIES: str = """
MATCH (reg:REGULATION {id: $regulation_id})
MATCH (reg)-[:APPLIES_TO]->(entity:ENTITY)
OPTIONAL MATCH (entity)-[:COMPLIES_WITH]->(obl:OBLIGATION)
RETURN entity.id AS entity_id,
       entity.name AS entity_name,
       entity.entity_type AS entity_type,
       collect(DISTINCT obl {.id, .title, .risk_weight}) AS compliance_obligations,
       CASE
           WHEN count(obl) = 0 THEN 'pending'
           ELSE 'assessed'
       END AS compliance_status
"""

GET_ENTITY_OBLIGATIONS: str = """
MATCH (entity:ENTITY {id: $entity_id})
OPTIONAL MATCH (entity)<-[:APPLIES_TO]-(reg:REGULATION)
OPTIONAL MATCH (reg)-[:CREATES_OBLIGATION]->(obl:OBLIGATION)
RETURN collect(DISTINCT {regulation_id: reg.id, regulation_code: reg.code, obligation: obl {.id, .title, .text, .risk_weight}}) AS obligations
"""

# ---------------------------------------------------------------------------
# Merge Operations (for bulk import)
# ---------------------------------------------------------------------------

MERGE_NODE: str = """
MERGE (n {id: $id})
ON CREATE SET
    n.node_type = $node_type,
    n.labels = $labels,
    n += $properties,
    n.valid_from = datetime($valid_from),
    n.valid_to = $valid_to,
    n.version = $version,
    n.created_at = datetime($created_at),
    n.updated_at = datetime($updated_at),
    n.embedding = $embedding
ON MATCH SET
    n += $properties,
    n.updated_at = datetime($updated_at),
    n.embedding = CASE WHEN $embedding IS NOT NULL THEN $embedding ELSE n.embedding END
RETURN n
"""

MERGE_RELATIONSHIP: str = """
MATCH (source {id: $source_id})
MATCH (target {id: $target_id})
MERGE (source)-[r:RELATIONSHIP {id: $id}]->(target)
ON CREATE SET
    r.rel_type = $rel_type,
    r.properties = $properties,
    r.valid_from = datetime($valid_from),
    r.valid_to = $valid_to,
    r.version = $version,
    r.created_at = datetime($created_at),
    r.updated_at = datetime($updated_at)
ON MATCH SET
    r.rel_type = $rel_type,
    r.properties = $properties,
    r.updated_at = datetime($updated_at),
    r.version = $version
RETURN r
"""


# ---------------------------------------------------------------------------
# Query builder helpers
# ---------------------------------------------------------------------------

def build_create_node_query(node_type: str) -> str:
    """Return the appropriate CREATE query for a given node type."""
    type_map = {
        "REGULATION": CREATE_REGULATION_NODE,
        "CLAUSE": CREATE_CLAUSE_NODE,
        "OBLIGATION": CREATE_OBLIGATION_NODE,
    }
    return type_map.get(node_type, CREATE_REGULATION_NODE)


def build_temporal_filter(
    alias: str = "n",
    as_of_param: str = "as_of",
) -> str:
    """Build a temporal filter clause for point-in-time queries."""
    return (
        f"({alias}.valid_from IS NULL OR {alias}.valid_from <= datetime(${as_of_param})) "
        f"AND ({alias}.valid_to IS NULL OR {alias}.valid_to > datetime(${as_of_param}))"
    )


# ---------------------------------------------------------------------------
# Schema Management
# ---------------------------------------------------------------------------

def build_schema_setup_queries() -> list[str]:
    """Return parameterized schema setup queries for all node and relationship types."""
    queries: list[str] = []
    node_labels = ["REGULATION", "CLAUSE", "OBLIGATION", "ENTITY", "AMENDMENT",
                   "EVENT", "RISK_FACTOR", "CONTROL", "POLICY", "PROCEDURE", "EVIDENCE"]
    for label in node_labels:
        queries.append(
            f"CREATE CONSTRAINT unique_{label.lower()}_id IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE n.id IS UNIQUE"
        )
        queries.append(
            f"CREATE INDEX {label.lower()}_valid_from IF NOT EXISTS "
            f"FOR (n:{label}) ON (n.valid_from)"
        )
        queries.append(
            f"CREATE INDEX {label.lower()}_version IF NOT EXISTS "
            f"FOR (n:{label}) ON (n.version)"
        )
    queries.append(
        "CREATE CONSTRAINT unique_rel_id IF NOT EXISTS "
        "FOR ()-[r:RELATIONSHIP]-() REQUIRE r.id IS UNIQUE"
    )
    queries.append(
        "CREATE INDEX rel_type_index IF NOT EXISTS "
        "FOR ()-[r:RELATIONSHIP]-() ON (r.rel_type)"
    )
    queries.append(
        "CREATE INDEX rel_valid_from_index IF NOT EXISTS "
        "FOR ()-[r:RELATIONSHIP]-() ON (r.valid_from)"
    )
    return queries

# ---------------------------------------------------------------------------
# Version Comparison
# ---------------------------------------------------------------------------

COMPARE_VERSIONS: str = """
MATCH (n {id: $node_id, version: $version_a})
MATCH (m {id: $node_id, version: $version_b})
RETURN n AS version_a_node,
       m AS version_b_node
"""

FIND_VERSION_DIFF: str = """
MATCH (n {id: $node_id})
WHERE n.version IN $versions
WITH n ORDER BY n.version ASC
WITH collect(n) AS versions
RETURN
    versions[0] AS earlier,
    versions[-1] AS later
"""

# ---------------------------------------------------------------------------
# Snapshot Operations
# ---------------------------------------------------------------------------

CREATE_SNAPSHOT: str = """
MATCH (n)
WHERE n.valid_from <= datetime($as_of)
  AND (n.valid_to IS NULL OR n.valid_to > datetime($as_of))
RETURN n AS snapshot_nodes
"""


def build_pagination_clause(
    page: int = 1,
    page_size: int = 20,
    _alias: str = "n",
) -> str:
    """Build SKIP / LIMIT clause for pagination."""
    skip = (page - 1) * page_size
    return f"SKIP {skip} LIMIT {page_size}"
