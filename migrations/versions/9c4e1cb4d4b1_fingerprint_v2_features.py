"""fingerprint_v2_features

Revision ID: 9c4e1cb4d4b1
Revises: f2b6c0a33d21
Create Date: 2026-04-12 18:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9c4e1cb4d4b1"
down_revision = "f2b6c0a33d21"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("link", schema=None) as batch_op:
        batch_op.add_column(sa.Column("followup_notified_at", sa.DateTime(), nullable=True))

    with op.batch_alter_table("visit", schema=None) as batch_op:
        batch_op.add_column(sa.Column("screen_depth", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("pixel_ratio", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("platform", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("touch_points", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("dark_mode", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("reduced_motion", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("connection_type", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("do_not_track", sa.String(length=8), nullable=True))
        batch_op.add_column(sa.Column("audio_fp", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("fonts", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("webgl_vendor", sa.String(length=256), nullable=True))
        batch_op.add_column(sa.Column("webgl_extensions_hash", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("webgl_max_texture", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("client_rects_fp", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("webrtc_ips", sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column("extensions_detected", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("taskbar_size", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("ua_brands", sa.String(length=256), nullable=True))


def downgrade():
    with op.batch_alter_table("visit", schema=None) as batch_op:
        batch_op.drop_column("ua_brands")
        batch_op.drop_column("taskbar_size")
        batch_op.drop_column("extensions_detected")
        batch_op.drop_column("webrtc_ips")
        batch_op.drop_column("client_rects_fp")
        batch_op.drop_column("webgl_max_texture")
        batch_op.drop_column("webgl_extensions_hash")
        batch_op.drop_column("webgl_vendor")
        batch_op.drop_column("fonts")
        batch_op.drop_column("audio_fp")
        batch_op.drop_column("do_not_track")
        batch_op.drop_column("connection_type")
        batch_op.drop_column("reduced_motion")
        batch_op.drop_column("dark_mode")
        batch_op.drop_column("touch_points")
        batch_op.drop_column("platform")
        batch_op.drop_column("pixel_ratio")
        batch_op.drop_column("screen_depth")

    with op.batch_alter_table("link", schema=None) as batch_op:
        batch_op.drop_column("followup_notified_at")
