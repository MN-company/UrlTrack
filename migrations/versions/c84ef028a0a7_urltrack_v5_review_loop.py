"""urltrack v5 review loop

Revision ID: c84ef028a0a7
Revises: 7a1f92b45e7c
Create Date: 2026-05-06 00:15:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "c84ef028a0a7"
down_revision = "7a1f92b45e7c"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("visit", schema=None) as batch_op:
        batch_op.add_column(sa.Column("review_label", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("review_note", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("reviewed_at", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("visit", schema=None) as batch_op:
        batch_op.drop_column("reviewed_at")
        batch_op.drop_column("review_note")
        batch_op.drop_column("review_label")
