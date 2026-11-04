"""Initial schema - all tables

Revision ID: 001_initial
Revises: None
Create Date: 2026-06-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create upload_status_enum type
    upload_status_enum = sa.Enum(
        "UPLOADED", "VALIDATED", "REJECTED", "QUARANTINED",
        name="upload_status_enum"
    )

    # Users table
    op.create_table(
        "users",
        sa.Column("user_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Roles table
    op.create_table(
        "roles",
        sa.Column("role_id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("role_name", sa.String(50), unique=True, nullable=False, index=True),
        sa.Column("description", sa.Text, nullable=True),
    )

    # User Roles junction table
    op.create_table(
        "user_roles",
        sa.Column(
            "user_id", UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "role_id", sa.Integer,
            sa.ForeignKey("roles.role_id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # User Sessions table
    op.create_table(
        "user_sessions",
        sa.Column("session_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("refresh_token_hash", sa.String(255), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Reports table
    op.create_table(
        "reports",
        sa.Column("report_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "uploaded_by", UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("stored_filename", sa.String(500), nullable=False),
        sa.Column("file_extension", sa.String(20), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("file_size", sa.BigInteger, nullable=False),
        sa.Column("sha256_hash", sa.String(64), nullable=False, index=True),
        sa.Column("page_count", sa.Integer, nullable=True),
        sa.Column("upload_status", upload_status_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Report Metadata table
    op.create_table(
        "report_metadata",
        sa.Column("metadata_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "report_id", UUID(as_uuid=True),
            sa.ForeignKey("reports.report_id", ondelete="CASCADE"),
            unique=True, nullable=False,
        ),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("author", sa.String(255), nullable=True),
        sa.Column("producer", sa.String(255), nullable=True),
        sa.Column("subject", sa.Text, nullable=True),
        sa.Column("keywords", sa.Text, nullable=True),
        sa.Column("creation_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("modification_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False),
    )

    # File Validation table
    op.create_table(
        "file_validation",
        sa.Column("validation_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "report_id", UUID(as_uuid=True),
            sa.ForeignKey("reports.report_id", ondelete="CASCADE"),
            unique=True, nullable=False,
        ),
        sa.Column("file_type_valid", sa.Boolean, default=False, nullable=False),
        sa.Column("malware_scan_status", sa.String(50), nullable=False),
        sa.Column("duplicate_status", sa.String(50), nullable=False),
        sa.Column("validation_status", sa.String(50), nullable=False),
        sa.Column("validation_notes", sa.Text, nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # File Storage table
    op.create_table(
        "file_storage",
        sa.Column("storage_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "report_id", UUID(as_uuid=True),
            sa.ForeignKey("reports.report_id", ondelete="CASCADE"),
            unique=True, nullable=False,
        ),
        sa.Column("encrypted_file_path", sa.String(1000), nullable=False),
        sa.Column("encryption_algorithm", sa.String(50), nullable=True),
        sa.Column("encryption_key_id", sa.String(255), nullable=True),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column("stored_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Audit Logs table
    op.create_table(
        "audit_logs",
        sa.Column("log_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "report_id", UUID(as_uuid=True),
            sa.ForeignKey("reports.report_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(100), nullable=False, index=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("details", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Security Events table
    op.create_table(
        "security_events",
        sa.Column("event_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("severity", sa.String(20), nullable=False, index=True),
        sa.Column("event_type", sa.String(100), nullable=False, index=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("security_events")
    op.drop_table("audit_logs")
    op.drop_table("file_storage")
    op.drop_table("file_validation")
    op.drop_table("report_metadata")
    op.drop_table("reports")
    op.drop_table("user_sessions")
    op.drop_table("user_roles")
    op.drop_table("roles")
    op.drop_table("users")

    # Drop enum
    sa.Enum(name="upload_status_enum").drop(op.get_bind(), checkfirst=True)
