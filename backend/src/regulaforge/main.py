"""RegulaForge CLI and API entry point.

Run API server:
    regulaforge api

Run CLI commands:
    regulaforge ingest crawl rbi
    regulaforge docintel process document.pdf
    regulaforge graphrag build --document-id doc1 --title "Title" --text "Text"
    regulaforge agents workflow --title "Analyze" --description "Task"

Or directly:
    python -m regulaforge.main api
    python -m regulaforge.main ingest crawl rbi
"""

import argparse
import asyncio
import logging
import sys

import uvicorn

from regulaforge.config.settings import settings


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="regulaforge",
        description="RegulaForge Enterprise AI Compliance Platform",
    )
    sub = parser.add_subparsers(dest="subsystem", required=True)

    # API server subcommand
    api_parser = sub.add_parser("api", help="Run the API server")
    api_parser.set_defaults(func=_run_api)

    # Subsystem CLIs
    from regulaforge.agents.interfaces.commands import create_agents_cli
    from regulaforge.document_intelligence.interfaces.commands import create_docintel_cli
    from regulaforge.graphrag.interfaces.commands import create_graphrag_cli
    from regulaforge.ingestion.interfaces.commands import create_ingestion_cli
    from regulaforge.ml.interfaces.commands import create_ml_cli

    create_ingestion_cli(sub)
    create_docintel_cli(sub)
    create_graphrag_cli(sub)
    create_agents_cli(sub)
    create_ml_cli(sub)

    return parser


def _run_api(_args: argparse.Namespace) -> None:
    uvicorn.run(
        "regulaforge.interfaces.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.is_development(),
        log_level=settings.log_level.value.lower(),
        access_log=True,
        workers=1 if settings.is_development() else None,
    )


SUBCOMMAND_MAP = {
    "ingest": "handle_ingestion_command",
    "docintel": "handle_docintel_command",
    "graphrag": "handle_graphrag_command",
    "agents": "handle_agents_command",
    "ml": "handle_ml_command",
}


async def _run_cli(args: argparse.Namespace) -> None:
    module_map = {
        "ingest": "regulaforge.ingestion.interfaces.commands",
        "docintel": "regulaforge.document_intelligence.interfaces.commands",
        "graphrag": "regulaforge.graphrag.interfaces.commands",
        "agents": "regulaforge.agents.interfaces.commands",
        "ml": "regulaforge.ml.interfaces.commands",
    }
    handler_name = SUBCOMMAND_MAP.get(args.subsystem)
    if handler_name is None:
        sys.exit(1)

    import importlib
    mod = importlib.import_module(module_map[args.subsystem])
    handler = getattr(mod, handler_name)
    await handler(args)


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )

    if args.subsystem == "api":
        _run_api(args)
    else:
        asyncio.run(_run_cli(args))


if __name__ == "__main__":
    main()
