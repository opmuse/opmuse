"""
tracks.scanned index

Revision ID: 2ec0152a1f
Revises: bb449587fe
Create Date: 2014-04-06 16:55:26.898299
"""

revision = '2ec0152a1f'
down_revision = 'bb449587fe'

from alembic import op


def upgrade():
    op.create_index('ix_tracks_scanned', 'tracks', ['scanned'])


def downgrade():
    op.drop_index('ix_tracks_scanned', 'tracks')
