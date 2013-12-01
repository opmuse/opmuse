"""
tracks.mode

Revision ID: 4a4e198884a
Revises: 51c9fb5ccdc
Create Date: 2013-12-01 17:58:09.810075
"""

revision = '4a4e198884a'
down_revision = '51c9fb5ccdc'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('tracks', sa.Column('mode', sa.String(16)))


def downgrade():
    pass
