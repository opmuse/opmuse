"""
users_and_albums

Revision ID: 77fc8b9f45
Revises: 2ec0152a1f
Create Date: 2014-04-18 18:52:12.767640
"""

revision = '77fc8b9f45'
down_revision = '2ec0152a1f'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        'users_and_albums',
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("album_id", sa.Integer, sa.ForeignKey('albums.id')),
        sa.Column("user_id", sa.Integer, sa.ForeignKey('users.id')),
        sa.Column("seen", sa.Boolean, default=False)
    )

    op.create_index('ix_users_and_albums_album_id_user_id', 'users_and_albums', ['album_id', 'user_id'], unique=True)
    op.create_index('ix_users_and_albums_seen', 'users_and_albums', ['seen'])


def downgrade():
    op.drop_table("users_and_albums")
