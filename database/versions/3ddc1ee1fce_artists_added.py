"""
artists.added

Revision ID: 3ddc1ee1fce
Revises: 25a9205e83c
Create Date: 2014-07-05 16:37:47.057973
"""

revision = '3ddc1ee1fce'
down_revision = '25a9205e83c'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql.expression import table, column


tracks = table('tracks',
    column('added', sa.DateTime),
    column('artist_id', sa.Integer),
)


artists = table('artists',
    column('id', sa.Integer),
    column('added', sa.DateTime)
)


def upgrade():
    op.add_column('artists', sa.Column('added', sa.DateTime, index=True))
    op.create_index('ix_artists_added', 'artists', ['added'])

    # migrate data
    op.execute(artists.update().values({
               'added': sa.select([sa.func.max(tracks.c.added)])
               .where(tracks.c.artist_id == artists.c.id)
               .as_scalar()}))


def downgrade():
    op.drop_column('artists', 'added')
