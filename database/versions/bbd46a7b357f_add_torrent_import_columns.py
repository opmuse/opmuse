"""
add torrent import columns

Revision ID: bbd46a7b357f
Revises: 10fd64ca216
Create Date: 2020-01-23 08:05:04.830570
"""

revision = 'bbd46a7b357f'
down_revision = '10fd64ca216'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('torrents', sa.Column('import_date', sa.DateTime))
    op.add_column('torrents', sa.Column('import_text', sa.String(255)))
    op.create_index('ix_torrents_import_date', 'torrents', ['import_date'])


def downgrade():
    op.drop_column('torrents', 'import_date')
    op.drop_column('torrents', 'import_text')
