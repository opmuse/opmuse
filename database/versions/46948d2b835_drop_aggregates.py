"""
drop aggregates

Revision ID: 46948d2b835
Revises: 5aa19dcfd99
Create Date: 2013-12-10 20:25:07.795804
"""

revision = '46948d2b835'
down_revision = '5aa19dcfd99'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.drop_column("artists", "added")
    op.drop_column("albums", "format")
    op.drop_column("albums", "track_count")
    op.drop_column("albums", "duration")
    op.drop_column("albums", "added")


def downgrade():
    pass
