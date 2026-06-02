"""add qr_config to link

Revision ID: b79f4d9a66c1
Revises: e8f2a91c7b6d
Create Date: 2026-06-02 00:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "b79f4d9a66c1"
down_revision = "e8f2a91c7b6d"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("link", schema=None) as batch_op:
        batch_op.add_column(sa.Column("qr_config", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("link", schema=None) as batch_op:
        batch_op.drop_column("qr_config")
