from __future__ import annotations

import contextlib
import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


def create_graphrag_cli(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "graphrag",
        help="GraphRAG operations: build, query, traverse, evaluate",
    )
    parser.set_defaults(command="graphrag")
    sub = parser.add_subparsers(dest="graphrag_command")

    build_parser = sub.add_parser("build", help="Build knowledge graph from document text")
    build_parser.add_argument("--document-id", required=True)
    build_parser.add_argument("--title", required=True)
    build_parser.add_argument("--text", required=True)
    build_parser.add_argument("--source", default="manual")
    build_parser.add_argument("--doc-type", default="regulation")
    build_parser.add_argument("--jurisdiction", default=None)
    build_parser.add_argument("--regulatory-body", default=None)
    build_parser.add_argument("--published-date", default=None)

    query_parser = sub.add_parser("query", help="Query the GraphRAG system")
    query_parser.add_argument("--query", required=True)
    query_parser.add_argument("--strategy", default="hybrid_full",
                              choices=[
                                  "vector_only", "bm25_only", "graph_only",
                                  "hybrid_vector_bm25", "hybrid_vector_graph",
                                  "hybrid_full",
                              ])
    query_parser.add_argument("--top-k", type=int, default=15)
    query_parser.add_argument("--output", choices=["text", "json"], default="text")

    traverse_parser = sub.add_parser("traverse", help="Traverse the knowledge graph")
    traverse_parser.add_argument("--entity", required=True)
    traverse_parser.add_argument("--max-depth", type=int, default=3)
    traverse_parser.add_argument("--max-branches", type=int, default=10)

    traverse_between_parser = sub.add_parser("traverse-between", help="Find path between two entities")
    traverse_between_parser.add_argument("--source", required=True)
    traverse_between_parser.add_argument("--target", required=True)
    traverse_between_parser.add_argument("--max-depth", type=int, default=4)

    temporal_parser = sub.add_parser("temporal", help="Query temporal events")
    temporal_parser.add_argument("--entity", required=True)
    temporal_parser.add_argument("--start-date", default=None)
    temporal_parser.add_argument("--end-date", default=None)

    evaluate_parser = sub.add_parser("evaluate", help="Run evaluation")
    evaluate_parser.add_argument("--test-file", help="JSON file with test queries and relevant IDs")
    evaluate_parser.add_argument("--queries", nargs="+", help="Test queries")
    evaluate_parser.add_argument("--output", default="json")

    sub.add_parser("status", help="Check GraphRAG system status")
    sub.add_parser("clear", help="Clear the knowledge graph")


async def _run_build(args: Any) -> None:
    from regulaforge.graphrag.interfaces.api import get_engine

    engine = await get_engine()
    published = None
    if args.published_date:
        with contextlib.suppress(ValueError):
            published = datetime.fromisoformat(args.published_date)
    await engine.graph_constructor.build_from_document(
        document_id=args.document_id,
        text=args.text,
        title=args.title,
        source=args.source,
        doc_type=args.doc_type,
        jurisdiction=args.jurisdiction,
        regulatory_body=args.regulatory_body,
        published_date=published,
    )


async def _run_query(args: Any) -> None:
    from regulaforge.graphrag.interfaces.api import get_engine

    engine = await get_engine()
    from regulaforge.graphrag.domain.enums import RetrievalStrategy

    strategy = RetrievalStrategy(args.strategy)
    context = await engine.hybrid_retriever.retrieve(
        query=args.query,
        strategy=strategy,
        top_k=args.top_k,
    )
    response = await engine.response_generator.generate(
        query=args.query,
        context=context,
    )
    await engine.groundedness_checker.check(response, context)

    if args.output == "json":
        pass
    else:
        pass


async def _run_traverse(args: Any) -> None:
    from regulaforge.graphrag.interfaces.api import get_engine

    engine = await get_engine()
    from regulaforge.graphrag.domain.models import TraversalConfig

    config = TraversalConfig(max_depth=args.max_depth, max_branches=args.max_branches)
    await engine.graph_traversal.traverse_from_entity(
        entity_name=args.entity, config=config
    )


async def _run_traverse_between(args: Any) -> None:
    from regulaforge.graphrag.interfaces.api import get_engine

    engine = await get_engine()
    path = await engine.graph_traversal.traverse_between(
        source_entity=args.source,
        target_entity=args.target,
        max_depth=args.max_depth,
    )
    if path is None:
        pass
    else:
        pass


async def _run_temporal(args: Any) -> None:
    from regulaforge.graphrag.interfaces.api import get_engine

    engine = await get_engine()
    start = datetime.fromisoformat(args.start_date) if args.start_date else None
    end = datetime.fromisoformat(args.end_date) if args.end_date else None
    await engine.temporal_graph.get_timeline(
        entity_name=args.entity,
        start_date=start,
        end_date=end,
    )


async def _run_evaluate(args: Any) -> None:
    from regulaforge.graphrag.interfaces.api import get_engine

    engine = await get_engine()
    if args.test_file:
        with open(args.test_file) as f:
            test_data = json.load(f)
        retrieval_data = []
        for item in test_data:
            context = await engine.hybrid_retriever.retrieve(
                query=item["query"],
                top_k=20,
            )
            retrieval_data.append((
                item["query"],
                context.results,
                set(item["relevant_ids"]),
            ))
        engine.evaluation.full_evaluation(
            retrieval_data=retrieval_data,
        )
    elif args.queries:
        return
    else:
        pass


async def _run_status(_args: Any) -> None:
    from regulaforge.graphrag.interfaces.api import get_engine

    engine = await get_engine()
    with contextlib.suppress(Exception):
        await engine.qdrant.collection_info()



async def _run_clear(_args: Any) -> None:
    from regulaforge.graphrag.interfaces.api import get_engine

    engine = await get_engine()
    await engine.neo4j.delete_all()


COMMAND_MAP = {
    "build": _run_build,
    "query": _run_query,
    "traverse": _run_traverse,
    "traverse-between": _run_traverse_between,
    "temporal": _run_temporal,
    "evaluate": _run_evaluate,
    "status": _run_status,
    "clear": _run_clear,
}


async def handle_graphrag_command(args: Any) -> None:
    cmd = getattr(args, "graphrag_command", None)
    if cmd and cmd in COMMAND_MAP:
        await COMMAND_MAP[cmd](args)
    else:
        pass
