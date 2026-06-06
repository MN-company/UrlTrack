"""add workspace multi-tenancy

Revision ID: 886dbffb9cf2
Revises: da7c3b6e8f10
Create Date: 2026-06-05 22:56:23.625856

"""
from alembic import op
import sqlalchemy as sa


revision = '886dbffb9cf2'
down_revision = 'da7c3b6e8f10'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('workspace',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('slug', sa.String(length=64), nullable=False),
        sa.Column('owner_user_id', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('settings_json', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
    )
    op.create_table('workspace_member',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=False),
        sa.Column('user_email', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=True),
        sa.Column('role', sa.String(length=32), nullable=False),
        sa.Column('invited_by', sa.String(length=255), nullable=True),
        sa.Column('invited_at', sa.DateTime(), nullable=False),
        sa.Column('joined_at', sa.DateTime(), nullable=True),
        sa.Column('invite_token', sa.String(length=128), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspace.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id', 'user_email', name='uq_workspace_member'),
    )

    with op.batch_alter_table('lead', schema=None) as batch_op:
        batch_op.add_column(sa.Column('workspace_id', sa.String(length=36), nullable=True))
        batch_op.create_index(batch_op.f('ix_lead_workspace_id'), ['workspace_id'], unique=False)
        batch_op.create_foreign_key('fk_lead_workspace_id', 'workspace', ['workspace_id'], ['id'], ondelete='SET NULL')

    with op.batch_alter_table('link', schema=None) as batch_op:
        batch_op.add_column(sa.Column('workspace_id', sa.String(length=36), nullable=True))
        batch_op.create_index(batch_op.f('ix_link_workspace_id'), ['workspace_id'], unique=False)
        batch_op.create_foreign_key('fk_link_workspace_id', 'workspace', ['workspace_id'], ['id'], ondelete='SET NULL')

    with op.batch_alter_table('visit', schema=None) as batch_op:
        batch_op.add_column(sa.Column('workspace_id', sa.String(length=36), nullable=True))
        batch_op.create_index(batch_op.f('ix_visit_workspace_id'), ['workspace_id'], unique=False)
        batch_op.create_foreign_key('fk_visit_workspace_id', 'workspace', ['workspace_id'], ['id'], ondelete='SET NULL')

    with op.batch_alter_table('visitor', schema=None) as batch_op:
        batch_op.add_column(sa.Column('workspace_id', sa.String(length=36), nullable=True))
        batch_op.create_index(batch_op.f('ix_visitor_workspace_id'), ['workspace_id'], unique=False)
        batch_op.create_foreign_key('fk_visitor_workspace_id', 'workspace', ['workspace_id'], ['id'], ondelete='SET NULL')

    with op.batch_alter_table('visitor_signal', schema=None) as batch_op:
        batch_op.add_column(sa.Column('workspace_id', sa.String(length=36), nullable=True))
        batch_op.create_index(batch_op.f('ix_visitor_signal_workspace_id'), ['workspace_id'], unique=False)
        batch_op.create_foreign_key('fk_visitor_signal_workspace_id', 'workspace', ['workspace_id'], ['id'], ondelete='SET NULL')


def downgrade():
    with op.batch_alter_table('visitor_signal', schema=None) as batch_op:
        batch_op.drop_constraint('fk_visitor_signal_workspace_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_visitor_signal_workspace_id'))
        batch_op.drop_column('workspace_id')

    with op.batch_alter_table('visitor', schema=None) as batch_op:
        batch_op.drop_constraint('fk_visitor_workspace_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_visitor_workspace_id'))
        batch_op.drop_column('workspace_id')

    with op.batch_alter_table('visit', schema=None) as batch_op:
        batch_op.drop_constraint('fk_visit_workspace_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_visit_workspace_id'))
        batch_op.drop_column('workspace_id')

    with op.batch_alter_table('link', schema=None) as batch_op:
        batch_op.drop_constraint('fk_link_workspace_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_link_workspace_id'))
        batch_op.drop_column('workspace_id')

    with op.batch_alter_table('lead', schema=None) as batch_op:
        batch_op.drop_constraint('fk_lead_workspace_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_lead_workspace_id'))
        batch_op.drop_column('workspace_id')

    op.drop_table('workspace_member')
    op.drop_table('workspace')
