"""thumbmark identity graph

Revision ID: e8f2a91c7b6d
Revises: 4e4c9a697305, c84ef028a0a7
Create Date: 2026-06-02 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "e8f2a91c7b6d"
down_revision = ("4e4c9a697305", "c84ef028a0a7")
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "visitor",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("first_seen", sa.DateTime(), nullable=True),
        sa.Column("last_seen", sa.DateTime(), nullable=True),
        sa.Column("probable_match_id", sa.String(length=36), nullable=True),
        sa.Column("primary_thumbmark_hash", sa.Text(), nullable=True),
        sa.Column("primary_thumbmark_visitor_id", sa.Text(), nullable=True),
        sa.Column("known_canvas_hashes", sa.Text(), nullable=True),
        sa.Column("known_audio_hashes", sa.Text(), nullable=True),
        sa.Column("known_webgl_vendors", sa.Text(), nullable=True),
        sa.Column("known_screen_profiles", sa.Text(), nullable=True),
        sa.Column("known_timezones", sa.Text(), nullable=True),
        sa.Column("known_languages", sa.Text(), nullable=True),
        sa.Column("known_thumbmark_visitor_ids", sa.Text(), nullable=True),
        sa.Column("thumbmark_api_calls_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("thumbmark_api_confidence_avg", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["probable_match_id"], ["visitor.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    with op.batch_alter_table("visit", schema=None) as batch_op:
        batch_op.add_column(sa.Column("visitor_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("probable_visitor_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("thumbmark_hash", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("thumbmark_raw", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("thumbmark_visitor_id", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("thumbmark_api_confidence", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("thumbmark_api_called", sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column("thumbmark_api_error", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("fp_audio_hash", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("fp_canvas_hash", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("fp_webgl_vendor", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("fp_webgl_hash", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("fp_fonts_hash", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("fp_screen_profile", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("fp_hardware_profile", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("fp_languages", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("fp_timezone", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("fp_speech_hash", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("fp_math_hash", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("fp_permissions_profile", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("fp_media_devices", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("fp_webrtc_ips", sa.Text(), nullable=True))
        batch_op.create_foreign_key("fk_visit_visitor_id", "visitor", ["visitor_id"], ["id"], ondelete="SET NULL")
        batch_op.create_foreign_key(
            "fk_visit_probable_visitor_id",
            "visitor",
            ["probable_visitor_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_visit_thumbmark_hash", ["thumbmark_hash"], unique=False)
        batch_op.create_index("ix_visit_thumbmark_visitor_id", ["thumbmark_visitor_id"], unique=False)
        batch_op.create_index("ix_visit_visitor_id", ["visitor_id"], unique=False)

    op.create_table(
        "visitor_signal",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("visitor_id", sa.String(length=36), nullable=False),
        sa.Column("visit_id", sa.Integer(), nullable=True),
        sa.Column("signal_type", sa.Text(), nullable=False),
        sa.Column("signal_value", sa.Text(), nullable=False),
        sa.Column("confidence_weight", sa.Integer(), nullable=False),
        sa.Column("first_seen", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["visit_id"], ["visit.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["visitor_id"], ["visitor.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("visitor_id", "signal_type", "signal_value", name="uq_visitor_signal_value"),
    )
    op.create_index("idx_visitor_signal_visitor", "visitor_signal", ["visitor_id"], unique=False)
    op.create_index("idx_visitor_signal_type_value", "visitor_signal", ["signal_type", "signal_value"], unique=False)


def downgrade():
    op.drop_index("idx_visitor_signal_type_value", table_name="visitor_signal")
    op.drop_index("idx_visitor_signal_visitor", table_name="visitor_signal")
    op.drop_table("visitor_signal")

    with op.batch_alter_table("visit", schema=None) as batch_op:
        batch_op.drop_index("ix_visit_visitor_id")
        batch_op.drop_index("ix_visit_thumbmark_visitor_id")
        batch_op.drop_index("ix_visit_thumbmark_hash")
        batch_op.drop_constraint("fk_visit_probable_visitor_id", type_="foreignkey")
        batch_op.drop_constraint("fk_visit_visitor_id", type_="foreignkey")
        batch_op.drop_column("fp_webrtc_ips")
        batch_op.drop_column("fp_media_devices")
        batch_op.drop_column("fp_permissions_profile")
        batch_op.drop_column("fp_math_hash")
        batch_op.drop_column("fp_speech_hash")
        batch_op.drop_column("fp_timezone")
        batch_op.drop_column("fp_languages")
        batch_op.drop_column("fp_hardware_profile")
        batch_op.drop_column("fp_screen_profile")
        batch_op.drop_column("fp_fonts_hash")
        batch_op.drop_column("fp_webgl_hash")
        batch_op.drop_column("fp_webgl_vendor")
        batch_op.drop_column("fp_canvas_hash")
        batch_op.drop_column("fp_audio_hash")
        batch_op.drop_column("thumbmark_api_error")
        batch_op.drop_column("thumbmark_api_called")
        batch_op.drop_column("thumbmark_api_confidence")
        batch_op.drop_column("thumbmark_visitor_id")
        batch_op.drop_column("thumbmark_raw")
        batch_op.drop_column("thumbmark_hash")
        batch_op.drop_column("probable_visitor_id")
        batch_op.drop_column("visitor_id")

    op.drop_table("visitor")
