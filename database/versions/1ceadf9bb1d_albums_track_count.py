"""
albums.track_count

Revision ID: 1ceadf9bb1d
Revises: 3e9ca5d1c1
Create Date: 2013-12-08 13:33:24.382594
"""

revision = '1ceadf9bb1d'
down_revision = '3e9ca5d1c1'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('albums', sa.Column('track_count', sa.Integer))


def downgrade():
    pass
