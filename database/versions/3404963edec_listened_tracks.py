"""
listened_tracks

Revision ID: 3404963edec
Revises: 77fc8b9f45
Create Date: 2014-04-21 13:43:32.351801
"""

revision = '3404963edec'
down_revision = '77fc8b9f45'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        'listened_tracks',
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255)),
        sa.Column("artist_name", sa.String(255)),
        sa.Column("album_name", sa.String(255)),
        sa.Column("timestamp", sa.Integer),
        sa.Column("user_id", sa.Integer, sa.ForeignKey('users.id')),
    )

    op.create_index('ix_listened_tracks_name', 'listened_tracks', ['name'])
    op.create_index('ix_listened_tracks_artist_name', 'listened_tracks', ['artist_name'])
    op.create_index('ix_listened_tracks_album_name', 'listened_tracks', ['album_name'])
    op.create_index('ix_listened_tracks_timestamp', 'listened_tracks', ['timestamp'])


def downgrade():
    op.drop_table("listened_tracks")
