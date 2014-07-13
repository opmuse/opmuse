"""
add users.active

Revision ID: 13d01b369a0
Revises: 3c44c019b14
Create Date: 2014-07-13 16:58:47.803906
"""

revision = '13d01b369a0'
down_revision = '3c44c019b14'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('users', sa.Column('active', sa.DateTime, index=True))
    op.create_index('ix_users_active', 'users', ['active'])


def downgrade():
    op.drop_column('users', 'active')
