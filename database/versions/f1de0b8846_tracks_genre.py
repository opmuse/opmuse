"""
tracks.genre

Revision ID: f1de0b8846
Revises: 46948d2b835
Create Date: 2014-01-19 10:32:42.124813
"""

revision = 'f1de0b8846'
down_revision = '46948d2b835'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('tracks', sa.Column('genre', sa.String(128)))


def downgrade():
    pass
