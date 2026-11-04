"""Add report_chunks table with pgvector

Revision ID: 007_add_report_chunks_pgvector
Revises: f5a1c2d3e4f6
Create Date: 2026-11-04 16:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    from sqlalchemy.types import UserDefinedType

    class Vector(UserDefinedType):
        def __init__(self, dim=1024):
            self.dim = dim

        def get_col_spec(self, **kw):
            return f"vector({self.dim})"


# revision identifiers, used by Alembic.
revision: str = '007_add_report_chunks_pgvector'
down_revision: Union[str, None] = 'f5a1c2d3e4f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Create report_chunks table
    op.create_table(
        'report_chunks',
        sa.Column('chunk_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('report_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('reports.report_id', ondelete='CASCADE'), nullable=False),
        sa.Column('section_id', sa.String(length=255), nullable=True),
        sa.Column('chunk', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(1024), nullable=True),
        sa.Column('chunk_index', sa.Integer(), nullable=True),
        sa.Column('context_prefix', sa.Text(), nullable=True),
        sa.Column('finding_id', sa.String(length=255), nullable=True),
        sa.Column('token_count', sa.Integer(), nullable=True),
        sa.Column('meta', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 3. Standard B-tree indexes for fast filtered lookups
    op.create_index('ix_report_chunks_report_id', 'report_chunks', ['report_id'])
    op.create_index('ix_report_chunks_section_id', 'report_chunks', ['section_id'])
    op.create_index('ix_report_chunks_finding_id', 'report_chunks', ['finding_id'])

    # 4. HNSW Vector index on cosine distance for high-performance approximate nearest neighbor search
    op.execute("CREATE INDEX IF NOT EXISTS ix_report_chunks_embedding ON report_chunks USING hnsw (embedding vector_cosine_ops);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_report_chunks_embedding;")
    op.drop_index('ix_report_chunks_finding_id', table_name='report_chunks')
    op.drop_index('ix_report_chunks_section_id', table_name='report_chunks')
    op.drop_index('ix_report_chunks_report_id', table_name='report_chunks')
    op.drop_table('report_chunks')

