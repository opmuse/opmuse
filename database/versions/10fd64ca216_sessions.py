"""
sessions

Revision ID: 10fd64ca216
Revises: 250258b8094
Create Date: 2015-07-18 17:55:03.529735
"""

revision = '10fd64ca216'
down_revision = '250258b8094'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


def upgrade():
    op.create_table(
        'sessions',
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("sess_id", sa.String(40)),
        sa.Column("data", sa.BLOB().with_variant(mysql.LONGBLOB(), 'mysql')),
        sa.Column("expiration_time", sa.DateTime),
        mysql_charset='utf8', mysql_engine='InnoDB'
    )

    op.create_index('ix_sessions_sess_id', 'sessions', ['sess_id'], unique=True)
    op.create_index('ix_sessions_expiration_time', 'sessions', ['expiration_time'])


def downgrade():
    op.drop_table("sessions")
