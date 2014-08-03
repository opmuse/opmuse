"""
rename tracks.upload_user_id to created_user_id

Revision ID: 186cdf63c34
Revises: df979ac853
Create Date: 2014-08-03 13:36:36.662934
"""

revision = '186cdf63c34'
down_revision = 'df979ac853'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql.expression import table, column


tracks = table('tracks',
    column('id', sa.Integer),
    column('upload_user_id', sa.Integer),
    column('created_user_id', sa.Integer),
)


def upgrade():
    op.add_column('tracks', sa.Column("created_user_id", sa.Integer,
                  sa.ForeignKey('users.id', name='fk_tracks_created_user_id')))
    op.execute(tracks.update().values({'created_user_id': tracks.c.upload_user_id}))
    op.drop_constraint('tracks_ibfk_3', 'tracks', type='foreignkey')
    op.drop_column('tracks', 'upload_user_id')


def downgrade():
    pass
