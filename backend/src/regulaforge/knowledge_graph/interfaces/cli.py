"""
Command-line interface for the Temporal Knowledge Graph.

Usage:
    python -m regulaforge.knowledge_graph.interfaces.cli setup-schema
    python -m regulaforge.knowledge_graph.interfaces.cli import <file>
    python -m regulaforge.knowledge_graph.interfaces.cli query <cypher>
    python -m regulaforge.knowledge_graph.interfaces.cli diff <node_id> <version_a> <version_b>
    python -m regulaforge.knowledge_graph.interfaces.cli find-duplicates [--type TYPE]
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

from regulaforge.config.logging import configure_logging
from regulaforge.config.settings import settings


@contextlib.asynccontextmanager
async def _adapter_lifecycle():
    """Connect to Neo4j, yield the adapter, disconnect on exit."""
    from regulaforge.knowledge_graph.infrastructure.neo4j_adapter import Neo4jAdapter

    adapter = Neo4jAdapter(
        uri=settings.neo4j.uri,
        user=settings.neo4j.user,
        password=settings.neo4j.password,
        database=settings.neo4j.database,
    )
    try:
        await adapter.connect()
        yield adapter
    finally:
        await adapter.disconnect()


async def cmd_setup_schema(_args: argparse.Namespace) -> None:
    """Create indexes and constraints in Neo4j."""
    async with _adapter_lifecycle() as adapter:
        result = await adapter.ensure_schema()
        print(f"Schema setup: {'success' if result['success'] else 'partial'}")
        print(f"  Constraints created: {result['constraints_created']}")
        print(f"  Indexes created: {result['indexes_created']}")
        if result["errors"]:
            print(f"  Errors ({len(result['errors'])}):")
            for err in result["errors"][:5]:
                print(f"    - {err}")


async def cmd_import(args: argparse.Namespace) -> None:
    """Import nodes and relationships from a JSON file."""
    from regulaforge.knowledge_graph.application.graph_service import KnowledgeGraphService
    from regulaforge.knowledge_graph.infrastructure.graph_embeddings import GraphEmbeddingService

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: file not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    async with _adapter_lifecycle() as adapter:
        embedding_service = GraphEmbeddingService()

        class _FakeEventPublisher:
            async def publish(self, _event: Any) -> None:
                pass

        service = KnowledgeGraphService(
            node_repo=adapter,
            rel_repo=adapter,
            query_repo=adapter,
            embedding_service=embedding_service,
            event_publisher=_FakeEventPublisher(),
        )

        source_type = args.source or "cli_import"
        stats = await service.merge_external_knowledge(
            source_type=source_type,
            source_data={"nodes": data.get("nodes", []), "relationships": data.get("relationships", [])},
        )
        print(f"Import from '{source_type}':")
        print(f"  Nodes created: {stats['nodes_created']}")
        print(f"  Relationships created: {stats['relationships_created']}")
        if stats["errors"]:
            print(f"  Errors ({stats['error_count']}):")
            for err in stats["errors"][:5]:
                print(f"    - {err}")


async def cmd_query(args: argparse.Namespace) -> None:
    """Execute a raw Cypher query."""
    async with _adapter_lifecycle() as adapter:
        results = await adapter.query_cypher(args.cypher)
        print(json.dumps(results, indent=2, default=str))


async def cmd_diff(args: argparse.Namespace) -> None:
    """Compare two versions of a node using the KnowledgeGraphService."""
    from regulaforge.knowledge_graph.application.graph_service import KnowledgeGraphService
    from regulaforge.knowledge_graph.infrastructure.graph_embeddings import GraphEmbeddingService

    async with _adapter_lifecycle() as adapter:
        service = KnowledgeGraphService(
            node_repo=adapter,
            rel_repo=adapter,
            query_repo=adapter,
            embedding_service=GraphEmbeddingService(),
        )
        node_id = UUID(args.node_id)
        version_a = int(args.version_a)
        version_b = int(args.version_b)

        result = await service.compare_versions(
            node_id=node_id,
            version_a=version_a,
            version_b=version_b,
        )
        diff = result["diff"]
        print(f"Node: {node_id}")
        print(f"Version {version_a} -> Version {version_b}")
        print(f"  Added: {diff['change_count']} changes")
        print(f"  Added properties: {len(diff['added'])}")
        print(f"  Removed properties: {len(diff['removed'])}")
        print(f"  Changed properties: {len(diff['changed'])}")
        if diff["added"]:
            print(f"  Added keys: {list(diff['added'].keys())}")
        if diff["removed"]:
            print(f"  Removed keys: {list(diff['removed'].keys())}")
        if diff["changed"]:
            print(f"  Changed keys: {list(diff['changed'].keys())}")


async def cmd_find_duplicates(args: argparse.Namespace) -> None:
    """Scan the graph for potential duplicate nodes."""
    from regulaforge.knowledge_graph.application.entity_resolution import EntityResolutionService
    from regulaforge.knowledge_graph.domain.models import GraphNodeType

    async with _adapter_lifecycle() as adapter:
        resolution_service = EntityResolutionService(
            node_repo=adapter,
            rel_repo=adapter,
            threshold=args.threshold,
        )

        node_type = GraphNodeType(args.type.upper()) if args.type else None
        candidates = await resolution_service.find_duplicates(node_type=node_type)

        print(f"Found {len(candidates)} duplicate candidates (threshold={args.threshold})")
        for i, cand in enumerate(candidates[:20]):
            source_title = cand.source.properties.get("title", str(cand.source.id))
            target_title = cand.target.properties.get("title", str(cand.target.id))
            print(f"  [{i + 1}] Score={cand.similarity_score:.3f} "
                  f"Fields={cand.match_fields}")
            print(f"       A: {source_title} ({cand.source.id})")
            print(f"       B: {target_title} ({cand.target.id})")
        if len(candidates) > 20:
            print(f"  ... and {len(candidates) - 20} more")


def main() -> None:
    configure_logging("KNOWLEDGE_GRAPH_CLI")
    parser = argparse.ArgumentParser(description="Knowledge Graph CLI")
    subparsers = parser.add_subparsers(dest="command")

    p = subparsers.add_parser("setup-schema", help="Create indexes and constraints")
    p = subparsers.add_parser("import", help="Import from JSON file")
    p.add_argument("file", type=str, help="Path to JSON file with nodes/relationships")
    p.add_argument("--source", type=str, default="cli_import", help="Source type label")

    p = subparsers.add_parser("query", help="Execute Cypher query")
    p.add_argument("cypher", type=str, help="Cypher query string")

    p = subparsers.add_parser("diff", help="Compare node versions")
    p.add_argument("node_id", type=str, help="Node UUID")
    p.add_argument("version_a", type=str, help="First version number")
    p.add_argument("version_b", type=str, help="Second version number")

    p = subparsers.add_parser("find-duplicates", help="Scan for duplicate nodes")
    p.add_argument("--type", type=str, default=None, help="Node type filter (e.g., REGULATION)")
    p.add_argument("--threshold", type=float, default=0.85, help="Similarity threshold (0-1)")
    p.add_argument("--merge", action="store_true", help="Auto-merge duplicates")

    args = parser.parse_args()
    if args.command == "setup-schema":
        import asyncio
        asyncio.run(cmd_setup_schema(args))
    elif args.command == "import":
        import asyncio
        asyncio.run(cmd_import(args))
    elif args.command == "query":
        import asyncio
        asyncio.run(cmd_query(args))
    elif args.command == "diff":
        import asyncio
        asyncio.run(cmd_diff(args))
    elif args.command == "find-duplicates":
        import asyncio
        asyncio.run(cmd_find_duplicates(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
