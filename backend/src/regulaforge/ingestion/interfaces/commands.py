"""
CLI for the RegulaForge ingestion subsystem.

Provides three sub-commands (crawl, list, stats) for local development
and debugging.  Production deployments should use the FastAPI router.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

from regulaforge.ingestion.domain.models import CrawlSourceConfig, CrawlSourceType
from regulaforge.ingestion.infrastructure.repositories.in_memory import (
    InMemoryCrawlJobRepository,
    InMemoryDocumentRepository,
    InMemoryFingerprintRepository,
)

logger = logging.getLogger(__name__)

DATA_DIR_DEFAULT = "./data"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="regulaforge-ingest",
        description="RegulaForge Data Ingestion CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    crawl_parser = sub.add_parser("crawl", help="Run a crawl for a regulatory source")
    crawl_parser.add_argument(
        "source",
        type=str,
        choices=[s.value for s in CrawlSourceType] + ["all"],
        help="Source to crawl",
    )
    crawl_parser.add_argument(
        "--incremental",
        action="store_true",
        default=True,
        help="Incremental crawl (default)",
    )
    crawl_parser.add_argument(
        "--full",
        action="store_true",
        help="Full crawl (ignore last run)",
    )
    crawl_parser.add_argument(
        "--data-dir",
        type=str,
        default=DATA_DIR_DEFAULT,
        help="Data directory",
    )

    list_parser = sub.add_parser("list", help="List documents")
    list_parser.add_argument(
        "--source",
        type=str,
        choices=[s.value for s in CrawlSourceType],
        help="Filter by source",
    )
    list_parser.add_argument("--limit", type=int, default=20, help="Limit results")
    list_parser.add_argument("--offset", type=int, default=0, help="Offset results")

    stats_parser = sub.add_parser("stats", help="Show ingestion statistics")
    stats_parser.add_argument(
        "--data-dir",
        type=str,
        default=DATA_DIR_DEFAULT,
        help="Data directory",
    )

    return parser


async def run_crawl(args: argparse.Namespace) -> None:
    from regulaforge.ingestion.application.crawler_service import CrawlerService
    from regulaforge.ingestion.infrastructure.crawlers.irdai_crawler import IRDAICrawler
    from regulaforge.ingestion.infrastructure.crawlers.rbi_crawler import RBICrawler
    from regulaforge.ingestion.infrastructure.crawlers.sebi_crawler import SEBICrawler
    from regulaforge.ingestion.infrastructure.storage.document_store import DocumentStore
    from regulaforge.ingestion.application.fingerprint_service import (
        DeduplicationService,
        FingerprintCalculator,
    )
    from regulaforge.ingestion.application.etl_service import ETLService

    data_dir = Path(args.data_dir)
    store = DocumentStore(data_dir)

    doc_repo = InMemoryDocumentRepository()
    job_repo = InMemoryCrawlJobRepository()
    fp_repo = InMemoryFingerprintRepository()

    fp_calc = FingerprintCalculator()
    dedup = DeduplicationService(fp_calc)
    etl = ETLService(doc_repo, fp_repo, job_repo, fp_calc, dedup)

    configs = {
        CrawlSourceType.RBI: CrawlSourceConfig(
            source_type=CrawlSourceType.RBI,
            base_url="https://www.rbi.org.in/Scripts/BSView.aspx",
            list_url="https://www.rbi.org.in/Scripts/BSView.aspx?mode=List",
        ),
        CrawlSourceType.SEBI: CrawlSourceConfig(
            source_type=CrawlSourceType.SEBI,
            base_url="https://www.sebi.gov.in/sebiweb/home/HomeAction.do",
            list_url="https://www.sebi.gov.in/sebiweb/home/list",
        ),
        CrawlSourceType.IRDAI: CrawlSourceConfig(
            source_type=CrawlSourceType.IRDAI,
            base_url="https://www.irdai.gov.in/",
            list_url="https://www.irdai.gov.in/ADMINCMS/modules/cms/",
        ),
    }

    crawlers = {
        CrawlSourceType.RBI: RBICrawler(),
        CrawlSourceType.SEBI: SEBICrawler(),
        CrawlSourceType.IRDAI: IRDAICrawler(),
    }

    # DocumentStore public API: raw_dir and text_dir are accessible via
    # dedicated properties for CLI usage.
    raw_dir = store.raw_dir
    text_dir = store.text_dir

    service = CrawlerService(
        crawlers=crawlers,
        doc_repo=doc_repo,
        fp_repo=fp_repo,
        job_repo=job_repo,
        etl_service=etl,
        fingerprint_calculator=fp_calc,
        configs=configs,
        raw_dir=raw_dir,
        text_dir=text_dir,
    )

    incremental = not args.full
    if args.source == "all":
        await service.crawl_all(incremental=incremental)
    else:
        source = CrawlSourceType(args.source)
        await service.crawl_source(source, incremental=incremental)


async def run_list(args: argparse.Namespace) -> None:
    repo = InMemoryDocumentRepository()
    docs, total = await repo.list(
        source_type=CrawlSourceType(args.source) if args.source else None,
        limit=args.limit,
        offset=args.offset,
    )
    logger.info("Total docs: %d", total)
    for _d in docs:
        pass


async def run_stats(args: argparse.Namespace) -> None:
    from regulaforge.ingestion.infrastructure.storage.document_store import DocumentStore

    DocumentStore(Path(args.data_dir))


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )

    if args.command == "crawl":
        asyncio.run(run_crawl(args))
    elif args.command == "list":
        asyncio.run(run_list(args))
    elif args.command == "stats":
        asyncio.run(run_stats(args))


if __name__ == "__main__":
    main()


def create_ingestion_cli(subparsers: Any) -> None:
    """Add ingestion subcommand to a parent argparse subparser group."""
    parser = subparsers.add_parser(
        "ingest",
        help="Ingestion operations: crawl, list, stats",
    )
    parser.set_defaults(subsystem="ingest")
    sub = parser.add_subparsers(dest="ingest_command", required=True)

    crawl_parser = sub.add_parser("crawl", help="Run a crawl for a regulatory source")
    crawl_parser.add_argument(
        "source",
        type=str,
        choices=[s.value for s in CrawlSourceType] + ["all"],
        help="Source to crawl",
    )
    crawl_parser.add_argument("--incremental", action="store_true", default=True, help="Incremental crawl")
    crawl_parser.add_argument("--full", action="store_true", help="Full crawl")
    crawl_parser.add_argument("--data-dir", type=str, default=DATA_DIR_DEFAULT, help="Data directory")

    list_parser = sub.add_parser("list", help="List documents")
    list_parser.add_argument("--source", type=str, choices=[s.value for s in CrawlSourceType], help="Filter by source")
    list_parser.add_argument("--limit", type=int, default=20, help="Limit results")
    list_parser.add_argument("--offset", type=int, default=0, help="Offset results")

    stats_parser = sub.add_parser("stats", help="Show ingestion statistics")
    stats_parser.add_argument("--data-dir", type=str, default=DATA_DIR_DEFAULT, help="Data directory")


INGEST_COMMAND_MAP = {
    "crawl": run_crawl,
    "list": run_list,
    "stats": run_stats,
}


async def handle_ingestion_command(args: Any) -> None:
    cmd = getattr(args, "ingest_command", None)
    if cmd and cmd in INGEST_COMMAND_MAP:
        await INGEST_COMMAND_MAP[cmd](args)
