"""
users_and_albums.seen to datetime

Revision ID: 11f76b5844
Revises: 3404963edec
Create Date: 2014-04-29 22:01:19.438391
"""

revision = '11f76b5844'
down_revision = '3404963edec'

import datetime
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql.expression import table, column


users_and_albums = table('users_and_albums',
    column('id', sa.Integer),
    column('new_seen', sa.DateTime),
    column('seen', sa.Boolean)
)


def upgrade():
    op.add_column('users_and_albums', sa.Column('new_seen', sa.DateTime))

    # migrate data
    op.execute(users_and_albums.update().values({
               'new_seen': datetime.datetime.utcnow()})
               .where(users_and_albums.c.seen == True))

    op.drop_column('users_and_albums', 'seen')
    op.alter_column('users_and_albums', 'new_seen', new_column_name='seen', existing_type=sa.DateTime)
    op.create_index('ix_albums_seen', 'users_and_albums', ['seen'])


def downgrade():
    pass
