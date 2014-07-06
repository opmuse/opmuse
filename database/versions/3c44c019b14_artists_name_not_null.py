"""
artists.name not null

Revision ID: 3c44c019b14
Revises: 3ddc1ee1fce
Create Date: 2014-07-06 15:23:41.062061
"""

revision = '3c44c019b14'
down_revision = '3ddc1ee1fce'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column("artists", "name", nullable=False, existing_type=sa.VARBINARY(255))


def downgrade():
    op.alter_column("artists", "name", nullable=True, existing_type=sa.VARBINARY(255))
