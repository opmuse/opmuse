"""
add users.created

Revision ID: 58eff9292ee
Revises: 13d01b369a0
Create Date: 2014-07-31 12:49:32.090524
"""

revision = '58eff9292ee'
down_revision = '13d01b369a0'

from alembic import op
import sqlalchemy as sa
import datetime
from sqlalchemy.sql.expression import table, column


users = table('users',
    column('id', sa.Integer),
    column('created', sa.DateTime)
)

def upgrade():
    op.add_column('users', sa.Column('created', sa.DateTime, index=True))
    op.create_index('ix_users_created', 'users', ['created'])

    op.execute(users.update().values({'created': datetime.datetime.now()}))


def downgrade():
    op.drop_column('users', 'created')
