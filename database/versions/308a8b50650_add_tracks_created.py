"""
add tracks.created

Revision ID: 308a8b50650
Revises: 58eff9292ee
Create Date: 2014-07-31 18:19:01.782752
"""

revision = '308a8b50650'
down_revision = '58eff9292ee'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql.expression import table, column


tracks = table('tracks',
    column('id', sa.Integer),
    column('created', sa.DateTime),
    column('added', sa.DateTime),
)


albums = table('albums',
    column('id', sa.Integer),
    column('created', sa.DateTime),
    column('added', sa.DateTime),
)


artists = table('artists',
    column('id', sa.Integer),
    column('created', sa.DateTime),
    column('added', sa.DateTime),
)


def upgrade():
    op.add_column('tracks', sa.Column('created', sa.DateTime, index=True))
    op.create_index('ix_tracks_created', 'tracks', ['created'])

    op.execute(tracks.update().values({'created': tracks.c.added}))

    op.add_column('albums', sa.Column('created', sa.DateTime, index=True))
    op.create_index('ix_albums_created', 'albums', ['created'])

    op.execute(albums.update().values({'created': albums.c.added}))

    op.add_column('artists', sa.Column('created', sa.DateTime, index=True))
    op.create_index('ix_artists_created', 'artists', ['created'])

    op.execute(artists.update().values({'created': artists.c.added}))


def downgrade():
    op.drop_column('tracks', 'created')
    op.drop_column('albums', 'created')
    op.drop_column('artists', 'created')
