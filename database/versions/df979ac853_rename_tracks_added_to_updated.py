"""
rename tracks.added to updated

Revision ID: df979ac853
Revises: 308a8b50650
Create Date: 2014-08-01 16:49:58.461867
"""

revision = 'df979ac853'
down_revision = '308a8b50650'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column('tracks', 'added', new_column_name='updated', existing_type=sa.DateTime)
    op.alter_column('albums', 'added', new_column_name='updated', existing_type=sa.DateTime)
    op.alter_column('artists', 'added', new_column_name='updated', existing_type=sa.DateTime)


def downgrade():
    op.alter_column('tracks', 'updated', new_column_name='added', existing_type=sa.DateTime)
    op.alter_column('albums', 'updated', new_column_name='added', existing_type=sa.DateTime)
    op.alter_column('artists', 'updated', new_column_name='added', existing_type=sa.DateTime)
