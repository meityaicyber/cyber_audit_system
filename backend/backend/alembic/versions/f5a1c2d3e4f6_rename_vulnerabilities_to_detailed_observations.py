"""rename vulnerabilities to detailed_observations

Revision ID: f5a1c2d3e4f6
Revises: faa6699324f2
Create Date: 2026-10-06 13:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f5a1c2d3e4f6'
down_revision: Union[str, None] = 'e1cdc4cfd568'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop old vulnerabilities table and its enum types
    op.drop_index(op.f('ix_vulnerabilities_status'), table_name='vulnerabilities', if_exists=True)
    op.drop_index(op.f('ix_vulnerabilities_severity'), table_name='vulnerabilities', if_exists=True)
    op.drop_index(op.f('ix_vulnerabilities_report_id'), table_name='vulnerabilities', if_exists=True)
    op.execute("DROP TABLE IF EXISTS vulnerabilities CASCADE")
    # Drop old enum types (ignore errors if they don't exist)
    op.execute("DROP TYPE IF EXISTS severity_level")
    op.execute("DROP TYPE IF EXISTS vuln_status")

    # Create new enum types
    observation_status = postgresql.ENUM(
        'Open', 'Closed', 'Partially Remediated',
        name='observation_status', create_type=False
    )
    observation_severity = postgresql.ENUM(
        'Critical', 'High', 'Medium', 'Low',
        name='observation_severity', create_type=False
    )
    observation_impact = postgresql.ENUM(
        'Major', 'Moderate', 'Minor',
        name='observation_impact', create_type=False
    )
    observation_likelihood = postgresql.ENUM(
        'Easy', 'Moderate', 'Hard',
        name='observation_likelihood', create_type=False
    )
    observation_new_repeat = postgresql.ENUM(
        'New', 'Repeat',
        name='observation_new_repeat', create_type=False
    )

    # Create enum types in DB
    observation_status.create(op.get_bind(), checkfirst=True)
    observation_severity.create(op.get_bind(), checkfirst=True)
    observation_impact.create(op.get_bind(), checkfirst=True)
    observation_likelihood.create(op.get_bind(), checkfirst=True)
    observation_new_repeat.create(op.get_bind(), checkfirst=True)

    # Create the detailed_observations table
    op.create_table(
        'detailed_observations',
        sa.Column('finding_id', sa.UUID(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('report_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('status', observation_status, nullable=True),
        sa.Column('severity', observation_severity, nullable=True),
        sa.Column('impact_level', observation_impact, nullable=True),
        sa.Column('likelihood_level', observation_likelihood, nullable=True),
        sa.Column('cve_id', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('cvss_score', sa.Numeric(precision=4, scale=1), nullable=True),
        sa.Column('cvss_vector', sa.Text(), nullable=True),
        sa.Column('severity_rationale', sa.Text(), nullable=True),
        sa.Column('reported_epss_score', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('observation_date', sa.Date(), nullable=True),
        sa.Column('cwe', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('affected_asset', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('regulatory_references', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('observation_description', sa.Text(), nullable=True),
        sa.Column('preconditions', sa.Text(), nullable=True),
        sa.Column('proof_of_concept', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('impact', sa.Text(), nullable=True),
        sa.Column('likely_root_cause', sa.Text(), nullable=True),
        sa.Column('recommendation', sa.Text(), nullable=True),
        sa.Column('reference', sa.Text(), nullable=True),
        sa.Column('new_or_repeat', observation_new_repeat, nullable=True),
        sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['report_id'], ['reports.report_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('finding_id')
    )
    op.create_index(op.f('ix_detailed_observations_report_id'), 'detailed_observations', ['report_id'], unique=False)
    op.create_index(op.f('ix_detailed_observations_severity'), 'detailed_observations', ['severity'], unique=False)
    op.create_index(op.f('ix_detailed_observations_status'), 'detailed_observations', ['status'], unique=False)


def downgrade() -> None:
    # Drop detailed_observations
    op.drop_index(op.f('ix_detailed_observations_status'), table_name='detailed_observations')
    op.drop_index(op.f('ix_detailed_observations_severity'), table_name='detailed_observations')
    op.drop_index(op.f('ix_detailed_observations_report_id'), table_name='detailed_observations')
    op.drop_table('detailed_observations')

    # Drop new enum types
    op.execute("DROP TYPE IF EXISTS observation_status")
    op.execute("DROP TYPE IF EXISTS observation_severity")
    op.execute("DROP TYPE IF EXISTS observation_impact")
    op.execute("DROP TYPE IF EXISTS observation_likelihood")
    op.execute("DROP TYPE IF EXISTS observation_new_repeat")

    # Recreate old vulnerabilities table
    op.create_table('vulnerabilities',
        sa.Column('vuln_id', sa.UUID(), nullable=False),
        sa.Column('report_id', sa.UUID(), nullable=False),
        sa.Column('vuln_seq_id', sa.SmallInteger(), nullable=True),
        sa.Column('vulnerability_title', sa.Text(), nullable=False),
        sa.Column('category', sa.Text(), nullable=True),
        sa.Column('severity', sa.Enum('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFORMATIONAL', name='severity_level', create_constraint=True), nullable=True),
        sa.Column('cvss_score', sa.Numeric(precision=3, scale=1), nullable=True),
        sa.Column('cve_ids', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('cwe_ids', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('affected_assets', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('status', sa.Enum('OPEN', 'CLOSED', 'ACCEPTED', 'RISK_ACCEPTED', 'IN_PROGRESS', name='vuln_status', create_constraint=True), nullable=True),
        sa.Column('new_or_repeat', sa.Text(), nullable=True),
        sa.Column('revalidation_status', sa.Text(), nullable=True),
        sa.Column('detailed_observation', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('impact', sa.Text(), nullable=True),
        sa.Column('recommendation', sa.Text(), nullable=True),
        sa.Column('proof_of_concept', sa.Text(), nullable=True),
        sa.Column('reproduction_steps', sa.Text(), nullable=True),
        sa.Column('reference', sa.Text(), nullable=True),
        sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['report_id'], ['reports.report_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('vuln_id')
    )
    op.create_index(op.f('ix_vulnerabilities_report_id'), 'vulnerabilities', ['report_id'], unique=False)
    op.create_index(op.f('ix_vulnerabilities_severity'), 'vulnerabilities', ['severity'], unique=False)
    op.create_index(op.f('ix_vulnerabilities_status'), 'vulnerabilities', ['status'], unique=False)
