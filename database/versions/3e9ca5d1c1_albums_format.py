"""
albums.format

Revision ID: 3e9ca5d1c1
Revises: 11ab1f81210
Create Date: 2013-12-08 13:33:11.415422
"""

revision = '3e9ca5d1c1'
down_revision = '11ab1f81210'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('albums', sa.Column('format', sa.String(128)))


def downgrade():
    pass
