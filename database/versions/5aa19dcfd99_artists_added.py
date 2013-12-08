"""
artists.added

Revision ID: 5aa19dcfd99
Revises: 176b25d58bb
Create Date: 2013-12-08 15:12:29.132917
"""

revision = '5aa19dcfd99'
down_revision = '176b25d58bb'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('artists', sa.Column('added', sa.DateTime, index=True))
    op.create_index('ix_artists_added', 'artists', ['added'])


def downgrade():
    pass
