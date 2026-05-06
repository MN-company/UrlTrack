"""urltrack v3 scoring lifecycle

Revision ID: 7a1f92b45e7c
Revises: 9c4e1cb4d4b1
Create Date: 2026-05-06 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "7a1f92b45e7c"
down_revision = "9c4e1cb4d4b1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("visit", schema=None) as batch_op:
        batch_op.add_column(sa.Column("fingerprint_version", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("fingerprint_composite_v1", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("identity_confidence", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("risk_score", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("match_reasons_json", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("cluster_conflict", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("conflict_reason", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("beacon_received_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("notification_sent_at", sa.DateTime(), nullable=True))
        batch_op.create_index("ix_visit_fingerprint_composite_v1", ["fingerprint_composite_v1"], unique=False)


def downgrade():
    with op.batch_alter_table("visit", schema=None) as batch_op:
        batch_op.drop_index("ix_visit_fingerprint_composite_v1")
        batch_op.drop_column("notification_sent_at")
        batch_op.drop_column("beacon_received_at")
        batch_op.drop_column("conflict_reason")
        batch_op.drop_column("cluster_conflict")
        batch_op.drop_column("match_reasons_json")
        batch_op.drop_column("risk_score")
        batch_op.drop_column("identity_confidence")
        batch_op.drop_column("fingerprint_composite_v1")
        batch_op.drop_column("fingerprint_version")
