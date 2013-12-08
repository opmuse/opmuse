"""
albums.added

Revision ID: 176b25d58bb
Revises: 1ceadf9bb1d
Create Date: 2013-12-08 13:33:39.727526
"""

revision = '176b25d58bb'
down_revision = '1ceadf9bb1d'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('albums', sa.Column('added', sa.DateTime))
    op.create_index('ix_albums_added', 'albums', ['added'])


def downgrade():
    pass
