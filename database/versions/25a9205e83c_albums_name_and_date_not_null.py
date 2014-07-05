"""
albums name and date not null

Revision ID: 25a9205e83c
Revises: 11f76b5844
Create Date: 2014-07-05 14:34:41.835997
"""

revision = '25a9205e83c'
down_revision = '11f76b5844'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql.expression import table, column


albums = table('albums',
    column('id', sa.Integer),
    column('date', sa.String(32))
)


def upgrade():
    # migrate data
    op.execute(albums.update().values({'date': ''}).where(albums.c.date is None))

    op.alter_column("albums", "name", nullable=False, existing_type=sa.VARBINARY(255))
    op.alter_column("albums", "date", nullable=False, existing_type=sa.String(32))


def downgrade():
    op.alter_column("albums", "name", nullable=True, existing_type=sa.VARBINARY(255))
    op.alter_column("albums", "date", nullable=True, existing_type=sa.String(32))
