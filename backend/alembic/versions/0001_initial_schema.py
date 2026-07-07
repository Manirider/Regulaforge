"""Initial database schema for RegulaForge platform.

Revision ID: 0001
Revises:
Create Date: 2026-07-04 11:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            comment="Unique tenant identifier",
        ),
        sa.Column("name", sa.String(200), nullable=False, comment="Organization name"),
        sa.Column(
            "slug", sa.String(100), nullable=False, comment="URL-friendly unique identifier"
        ),
        sa.Column(
            "domain",
            sa.String(255),
            nullable=True,
            comment="Organization domain for SSO/email matching",
        ),
        sa.Column(
            "settings",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Tenant-specific configuration",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Whether the tenant is active",
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="User who created this tenant",
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="User who last updated this tenant",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record creation timestamp (UTC)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record last update timestamp (UTC)",
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Optimistic concurrency version",
        ),
        sa.UniqueConstraint("name", name="uq_tenants_name"),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
        sa.Index("ix_tenants_is_active", "is_active"),
        sa.Index("ix_tenants_domain", "domain"),
        comment="Organization workspaces that isolate users and data",
    )

    op.create_table(
        "roles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            comment="Unique role identifier",
        ),
        sa.Column("name", sa.String(100), nullable=False, comment="Unique role name"),
        sa.Column(
            "description", sa.Text(), nullable=True, comment="Role description and purpose"
        ),
        sa.Column(
            "permissions",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="List of permission strings granted by this role",
        ),
        sa.Column(
            "is_system_role",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="System-defined roles are immutable",
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="User who created this role",
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="User who last updated this role",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record creation timestamp (UTC)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record last update timestamp (UTC)",
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Optimistic concurrency version",
        ),
        sa.UniqueConstraint("name", name="uq_roles_name"),
        sa.Index("ix_roles_is_system_role", "is_system_role"),
        comment="RBAC roles with associated permissions",
    )

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            comment="Unique user identifier",
        ),
        sa.Column(
            "email", sa.String(255), nullable=False, comment="User email address (used for login)"
        ),
        sa.Column("username", sa.String(150), nullable=False, comment="Unique username"),
        sa.Column(
            "password_hash",
            sa.String(255),
            nullable=True,
            comment="BCrypt password hash",
        ),
        sa.Column(
            "full_name", sa.String(255), nullable=True, comment="User display name"
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Whether the user account is active",
        ),
        sa.Column(
            "is_superuser",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="System-wide administrator flag",
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="SET NULL"),
            nullable=True,
            comment="Owning tenant identifier",
        ),
        sa.Column(
            "last_login_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last successful login timestamp (UTC)",
        ),
        sa.Column(
            "failed_login_attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Consecutive failed login count",
        ),
        sa.Column(
            "locked_until",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Account lockout expiration (UTC)",
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="User who created this record",
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="User who last updated this record",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record creation timestamp (UTC)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record last update timestamp (UTC)",
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Optimistic concurrency version",
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.Index("ix_users_tenant_id", "tenant_id"),
        sa.Index("ix_users_is_active", "is_active"),
        sa.Index("ix_users_is_superuser", "is_superuser"),
        sa.Index("ix_users_last_login_at", "last_login_at"),
        sa.Index("ix_users_locked_until", "locked_until"),
        comment="Platform users with authentication credentials",
    )

    op.create_table(
        "user_roles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            comment="Assignment identifier",
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            comment="User receiving the role",
        ),
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            nullable=False,
            comment="Role being assigned",
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
            comment="Tenant scope (None for global roles)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record creation timestamp (UTC)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record last update timestamp (UTC)",
        ),
        sa.UniqueConstraint(
            "user_id", "role_id", "tenant_id", name="uq_user_role_tenant"
        ),
        sa.Index("ix_user_roles_user_id", "user_id"),
        sa.Index("ix_user_roles_role_id", "role_id"),
        sa.Index("ix_user_roles_tenant_id", "tenant_id"),
        comment="Many-to-many relationship between users and roles",
    )

    op.create_table(
        "regulations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            comment="Unique regulation identifier",
        ),
        sa.Column("title", sa.String(500), nullable=False, comment="Regulation title"),
        sa.Column(
            "code", sa.String(50), nullable=False, comment="Unique regulation code (e.g., GDPR)"
        ),
        sa.Column(
            "description", sa.Text(), nullable=False, comment="Detailed regulation description"
        ),
        sa.Column("category", sa.String(50), nullable=False, comment="Regulation category"),
        sa.Column(
            "jurisdiction", sa.String(50), nullable=False, comment="Applicable jurisdiction"
        ),
        sa.Column(
            "issuing_body", sa.String(200), nullable=False, comment="Regulatory body name"
        ),
        sa.Column(
            "effective_date", sa.Date(), nullable=False, comment="Date regulation takes effect"
        ),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'draft'"),
            comment="Regulation lifecycle status",
        ),
        sa.Column(
            "version_str",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'1.0'"),
            comment="Regulation version",
        ),
        sa.Column(
            "tags",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Searchable tags",
        ),
        sa.Column(
            "parent_regulation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("regulations.id", ondelete="SET NULL"),
            nullable=True,
            comment="Parent regulation if this is an amendment",
        ),
        sa.Column(
            "superseded_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("regulations.id", ondelete="SET NULL"),
            nullable=True,
            comment="Regulation that supersedes this one",
        ),
        sa.Column(
            "metadata",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Flexible metadata",
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="User who created this record",
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="User who last updated this record",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record creation timestamp (UTC)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record last update timestamp (UTC)",
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Optimistic concurrency version",
        ),
        sa.UniqueConstraint("code", name="uq_regulations_code"),
        sa.Index("ix_regulations_status", "status"),
        sa.Index("ix_regulations_category", "category"),
        sa.Index("ix_regulations_jurisdiction", "jurisdiction"),
        sa.Index("ix_regulations_issuing_body", "issuing_body"),
        sa.Index("ix_regulations_effective_date", "effective_date"),
        comment="Regulatory documents, laws, standards, and policies",
    )

    op.create_table(
        "regulation_requirements",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            comment="Requirement identifier",
        ),
        sa.Column(
            "regulation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("regulations.id", ondelete="CASCADE"),
            nullable=False,
            comment="Parent regulation",
        ),
        sa.Column(
            "code",
            sa.String(100),
            nullable=False,
            comment="Requirement code within regulation",
        ),
        sa.Column("title", sa.String(500), nullable=False, comment="Requirement title"),
        sa.Column(
            "description", sa.Text(), nullable=False, comment="Requirement description"
        ),
        sa.Column(
            "parent_requirement_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("regulation_requirements.id", ondelete="SET NULL"),
            nullable=True,
            comment="Parent requirement if hierarchical",
        ),
        sa.Column(
            "is_mandatory",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Whether requirement is mandatory",
        ),
        sa.Column(
            "risk_weight",
            sa.Float(),
            nullable=False,
            server_default=sa.text("1.0"),
            comment="Risk weight (0.0 to 1.0)",
        ),
        sa.Column(
            "guidance", sa.Text(), nullable=True, comment="Implementation guidance"
        ),
        sa.Column(
            "references",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Reference links",
        ),
        sa.Column(
            "order_index",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Display ordering",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record creation timestamp (UTC)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record last update timestamp (UTC)",
        ),
        sa.UniqueConstraint(
            "regulation_id", "code", name="uq_req_regulation_code"
        ),
        sa.Index("ix_requirements_regulation_id", "regulation_id"),
        comment="Individual requirements within regulations",
    )

    op.create_table(
        "assessable_entities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            comment="Entity identifier",
        ),
        sa.Column("name", sa.String(200), nullable=False, comment="Entity name"),
        sa.Column(
            "entity_type", sa.String(50), nullable=False, comment="Entity type classification"
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Owning tenant ID",
        ),
        sa.Column(
            "description", sa.Text(), nullable=True, comment="Entity description"
        ),
        sa.Column(
            "parent_entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assessable_entities.id", ondelete="SET NULL"),
            nullable=True,
            comment="Parent entity in hierarchy",
        ),
        sa.Column(
            "tags",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Searchable tags",
        ),
        sa.Column(
            "attributes",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Flexible entity attributes",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Whether entity is active",
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Creator user ID",
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Last modifier user ID",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record creation timestamp (UTC)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record last update timestamp (UTC)",
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Optimistic concurrency version",
        ),
        sa.UniqueConstraint("tenant_id", "name", name="uq_entity_tenant_name"),
        sa.Index("ix_entities_tenant_id", "tenant_id"),
        sa.Index("ix_entities_type", "entity_type"),
        sa.Index("ix_entities_parent", "parent_entity_id"),
        sa.Index("ix_entities_active", "is_active"),
        comment="Entities subject to compliance assessment",
    )

    op.create_table(
        "compliance_assessments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            comment="Assessment identifier",
        ),
        sa.Column("title", sa.String(500), nullable=False, comment="Assessment title"),
        sa.Column(
            "entity_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Assessed entity ID",
        ),
        sa.Column(
            "entity_type", sa.String(50), nullable=False, comment="Type of assessed entity"
        ),
        sa.Column(
            "assessor_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Assessor user ID",
        ),
        sa.Column(
            "due_date", sa.Date(), nullable=False, comment="Assessment due date"
        ),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'scheduled'"),
            comment="Assessment status",
        ),
        sa.Column(
            "scope_description", sa.Text(), nullable=True, comment="Assessment scope"
        ),
        sa.Column(
            "overall_score",
            sa.Float(),
            nullable=True,
            comment="Final compliance score (0-100)",
        ),
        sa.Column(
            "approved_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Reviewer who approved",
        ),
        sa.Column(
            "approved_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Approval timestamp",
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Completion timestamp",
        ),
        sa.Column(
            "metadata",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Flexible metadata",
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Creator user ID",
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Last modifier user ID",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record creation timestamp (UTC)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record last update timestamp (UTC)",
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Optimistic concurrency version",
        ),
        sa.Index("ix_assessments_entity_id", "entity_id"),
        sa.Index("ix_assessments_status", "status"),
        sa.Index("ix_assessments_assessor", "assessor_id"),
        sa.Index("ix_assessments_due_date", "due_date"),
        sa.Index("ix_assessments_entity_status", "entity_id", "status"),
        comment="Compliance assessments evaluating entities against regulations",
    )

    op.create_table(
        "compliance_findings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            comment="Finding identifier",
        ),
        sa.Column(
            "assessment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("compliance_assessments.id", ondelete="CASCADE"),
            nullable=False,
            comment="Parent assessment",
        ),
        sa.Column(
            "requirement_code",
            sa.String(100),
            nullable=False,
            comment="Related requirement code",
        ),
        sa.Column("title", sa.String(500), nullable=False, comment="Finding title"),
        sa.Column(
            "description", sa.Text(), nullable=False, comment="Detailed finding description"
        ),
        sa.Column(
            "risk_level", sa.String(50), nullable=False, comment="Risk severity level"
        ),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'open'"),
            comment="Finding status",
        ),
        sa.Column(
            "impact_score", sa.Float(), nullable=True, comment="Impact score (0-10)"
        ),
        sa.Column(
            "likelihood_score",
            sa.Float(),
            nullable=True,
            comment="Likelihood score (0-10)",
        ),
        sa.Column(
            "remediation_recommendation",
            sa.Text(),
            nullable=True,
            comment="Suggested remediation",
        ),
        sa.Column(
            "remediation_due_date",
            sa.Date(),
            nullable=True,
            comment="Remediation deadline",
        ),
        sa.Column(
            "assigned_to",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Remediation assignee",
        ),
        sa.Column(
            "category", sa.String(100), nullable=True, comment="Finding category"
        ),
        sa.Column(
            "evidence",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Evidence artifacts",
        ),
        sa.Column(
            "resolved_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Resolution timestamp",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record creation timestamp (UTC)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record last update timestamp (UTC)",
        ),
        sa.Index("ix_findings_assessment_id", "assessment_id"),
        sa.Index("ix_findings_risk_level", "risk_level"),
        sa.Index("ix_findings_status", "status"),
        sa.Index("ix_findings_assigned_to", "assigned_to"),
        comment="Findings identified during compliance assessments",
    )

    op.create_table(
        "assessment_regulations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            comment="Link record identifier",
        ),
        sa.Column(
            "assessment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("compliance_assessments.id", ondelete="CASCADE"),
            nullable=False,
            comment="Assessment reference",
        ),
        sa.Column(
            "regulation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("regulations.id", ondelete="CASCADE"),
            nullable=False,
            comment="Regulation reference",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record creation timestamp (UTC)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record last update timestamp (UTC)",
        ),
        sa.UniqueConstraint(
            "assessment_id", "regulation_id", name="uq_assessment_regulation"
        ),
        sa.Index("ix_assessment_regs_regulation", "regulation_id"),
        comment="Many-to-many link between assessments and regulations",
    )

    op.create_table(
        "documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            comment="Document identifier",
        ),
        sa.Column("title", sa.String(500), nullable=False, comment="Document title"),
        sa.Column(
            "file_name", sa.String(500), nullable=False, comment="Original file name"
        ),
        sa.Column(
            "file_path", sa.String(2000), nullable=False, comment="Storage path"
        ),
        sa.Column("mime_type", sa.String(200), nullable=False, comment="MIME type"),
        sa.Column(
            "file_size_bytes",
            sa.Integer(),
            nullable=False,
            comment="File size in bytes",
        ),
        sa.Column(
            "artifact_type",
            sa.String(50),
            nullable=False,
            comment="Artifact classification",
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Owning tenant",
        ),
        sa.Column(
            "uploaded_by",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Uploading user",
        ),
        sa.Column(
            "description", sa.Text(), nullable=True, comment="Document description"
        ),
        sa.Column(
            "tags",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Searchable tags",
        ),
        sa.Column(
            "checksum",
            sa.String(128),
            nullable=True,
            comment="File checksum (SHA-256)",
        ),
        sa.Column(
            "metadata",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Flexible metadata",
        ),
        sa.Column(
            "is_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Verification status",
        ),
        sa.Column(
            "verified_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Verifier user ID",
        ),
        sa.Column(
            "verified_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Verification timestamp",
        ),
        sa.Column(
            "processing_status",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'pending'"),
            comment="AI processing status",
        ),
        sa.Column(
            "extracted_text",
            sa.Text(),
            nullable=True,
            comment="AI-extracted text content",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record creation timestamp (UTC)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record last update timestamp (UTC)",
        ),
        sa.Index("ix_documents_tenant_id", "tenant_id"),
        sa.Index("ix_documents_uploaded_by", "uploaded_by"),
        sa.Index("ix_documents_artifact_type", "artifact_type"),
        sa.Index("ix_documents_processing_status", "processing_status"),
        sa.Index("ix_documents_checksum", "checksum"),
        comment="Evidence documents and reference materials",
    )


def downgrade() -> None:
    op.drop_table("documents")
    op.drop_table("assessment_regulations")
    op.drop_table("compliance_findings")
    op.drop_table("compliance_assessments")
    op.drop_table("assessable_entities")
    op.drop_table("regulation_requirements")
    op.drop_table("regulations")
    op.drop_table("user_roles")
    op.drop_table("users")
    op.drop_table("roles")
    op.drop_table("tenants")
