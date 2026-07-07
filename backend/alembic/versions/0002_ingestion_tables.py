"""Add ingestion tables for regulatory document crawling.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-04 13:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "crawl_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            comment="Job identifier",
        ),
        sa.Column("source_type", sa.String(20), nullable=False, comment="Regulatory source (rbi, sebi, irdai)"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True, comment="Crawl start timestamp"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True, comment="Crawl end timestamp"),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'"), comment="Job status"),
        sa.Column("documents_found", sa.Integer(), nullable=False, server_default=sa.text("0"), comment="Documents discovered"),
        sa.Column("documents_downloaded", sa.Integer(), nullable=False, server_default=sa.text("0"), comment="Documents downloaded"),
        sa.Column("documents_failed", sa.Integer(), nullable=False, server_default=sa.text("0"), comment="Documents failed"),
        sa.Column("documents_duplicate", sa.Integer(), nullable=False, server_default=sa.text("0"), comment="Duplicate documents skipped"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="Error details if failed"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="Record creation timestamp (UTC)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="Record last update timestamp (UTC)",
        ),
        sa.Index("ix_crawl_jobs_source_type", "source_type"),
        sa.Index("ix_crawl_jobs_status", "status"),
        sa.Index("ix_crawl_jobs_created_at", "created_at"),
        comment="Regulatory crawl job tracking",
    )

    op.create_table(
        "regulatory_documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            comment="Document identifier",
        ),
        sa.Column("source_type", sa.String(20), nullable=False, comment="Regulatory source"),
        sa.Column("external_id", sa.String(200), nullable=False, comment="Source-specific identifier"),
        sa.Column("title", sa.String(1000), nullable=False, comment="Document title"),
        sa.Column("category", sa.String(50), nullable=False, server_default=sa.text("'other'"), comment="Document category"),
        sa.Column("url", sa.String(2000), nullable=False, comment="Source URL"),
        sa.Column("published_date", sa.DateTime(timezone=True), nullable=False, comment="Publication date"),
        sa.Column("effective_date", sa.DateTime(timezone=True), nullable=True, comment="Effective/implementation date"),
        sa.Column("download_path", sa.String(2000), nullable=True, comment="Local storage path"),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True, comment="File size in bytes"),
        sa.Column("file_hash_sha256", sa.String(64), nullable=True, comment="SHA-256 of raw file"),
        sa.Column("content_hash", sa.String(64), nullable=True, comment="SHA-256 of normalized text"),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb"), comment="Extracted metadata"),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'pending_download'"), comment="Processing status"),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1"), comment="Document version number"),
        sa.Column("previous_version_id", postgresql.UUID(as_uuid=True), nullable=True, comment="Previous version document ID"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="Record creation timestamp (UTC)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="Record last update timestamp (UTC)",
        ),
        sa.Index("ix_regdocs_source_external", "source_type", "external_id"),
        sa.Index("ix_regdocs_source_type", "source_type"),
        sa.Index("ix_regdocs_status", "status"),
        sa.Index("ix_regdocs_published_date", "published_date"),
        sa.Index("ix_regdocs_file_hash", "file_hash_sha256"),
        sa.Index("ix_regdocs_content_hash", "content_hash"),
        comment="Regulatory documents ingested from Indian regulators",
    )

    op.create_table(
        "document_fingerprints",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            comment="Fingerprint identifier",
        ),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False, comment="Regulatory document ID"),
        sa.Column("file_hash_sha256", sa.String(64), nullable=False, comment="SHA-256 of raw file"),
        sa.Column("content_hash", sa.String(64), nullable=False, comment="SHA-256 of normalized text"),
        sa.Column("simhash", sa.BigInteger(), nullable=True, comment="SimHash fingerprint (64-bit)"),
        sa.Column("num_tokens", sa.Integer(), nullable=False, server_default=sa.text("0"), comment="Number of tokens"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="Record creation timestamp (UTC)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="Record last update timestamp (UTC)",
        ),
        sa.Index("ix_fingerprints_document_id", "document_id"),
        sa.Index("ix_fingerprints_file_hash", "file_hash_sha256"),
        sa.Index("ix_fingerprints_content_hash", "content_hash"),
        comment="Document fingerprints for deduplication",
    )


def downgrade() -> None:
    op.drop_table("document_fingerprints")
    op.drop_table("regulatory_documents")
    op.drop_table("crawl_jobs")
