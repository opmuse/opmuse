"""
albums.duration

Revision ID: 11ab1f81210
Revises: 4a4e198884a
Create Date: 2013-12-07 12:29:32.714327
"""

revision = '11ab1f81210'
down_revision = '4a4e198884a'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('albums', sa.Column('duration', sa.Integer))


def downgrade():
    pass
