"""add dwell_ms

Revision ID: f2b6c0a33d21
Revises: fd60bee6230d
Create Date: 2026-04-12 16:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f2b6c0a33d21"
down_revision = "fd60bee6230d"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("visit", schema=None) as batch_op:
        batch_op.add_column(sa.Column("dwell_ms", sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table("visit", schema=None) as batch_op:
        batch_op.drop_column("dwell_ms")
