"""
albums.added aggregated column

Revision ID: bb449587fe
Revises: f1de0b8846
Create Date: 2014-04-06 10:59:11.911635
"""

revision = 'bb449587fe'
down_revision = 'f1de0b8846'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql.expression import table, column


tracks = table('tracks',
    column('added', sa.DateTime),
    column('album_id', sa.Integer),
)


albums = table('albums',
    column('id', sa.Integer),
    column('added', sa.DateTime)
)


def upgrade():
    op.add_column('albums', sa.Column('added', sa.DateTime, index=True))
    op.create_index('ix_albums_added', 'albums', ['added'])

    # migrate data
    op.execute(albums.update().values({
               'added': sa.select([sa.func.max(tracks.c.added)])
               .where(tracks.c.album_id == albums.c.id)
               .as_scalar()}))


def downgrade():
    op.drop_column('albums', 'added')
