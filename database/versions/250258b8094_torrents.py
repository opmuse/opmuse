"""
torrents

Revision ID: 250258b8094
Revises: 186cdf63c34
Create Date: 2015-05-17 19:06:16.578761
"""

revision = '250258b8094'
down_revision = '186cdf63c34'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        'torrents',
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('torrent_id', sa.String(40)),
        sa.Column('name', sa.String(255)),
        sa.Column('has_supported_files', sa.Boolean, default=False),
        sa.Column('added', sa.DateTime),
        sa.Column('size', sa.BigInteger),
        sa.Column('paused', sa.Boolean, default=False),
        sa.Column('finished', sa.Boolean, default=False),
        sa.Column('progress', sa.Numeric(precision=4, scale=1, asdecimal=True)),
        sa.Column('import_status', sa.String(128), default='', nullable=False),
        mysql_charset='utf8', mysql_engine='InnoDB'
    )

    op.create_index('ix_torrents_torrent_id', 'torrents', ['torrent_id'], unique=True)
    op.create_index('ix_torrents_finished', 'torrents', ['finished'])
    op.create_index('ix_torrents_paused', 'torrents', ['paused'])
    op.create_index('ix_torrents_added', 'torrents', ['added'])


def downgrade():
    op.drop_table("torrents")
