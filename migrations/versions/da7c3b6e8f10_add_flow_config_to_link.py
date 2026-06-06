"""add flow_config to link

Revision ID: da7c3b6e8f10
Revises: b79f4d9a66c1
Create Date: 2026-06-05 16:45:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "da7c3b6e8f10"
down_revision = "b79f4d9a66c1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("link", schema=None) as batch_op:
        batch_op.add_column(sa.Column("flow_config", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("link", schema=None) as batch_op:
        batch_op.drop_column("flow_config")
