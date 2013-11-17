import os.path
from alembic import context
from sqlalchemy import engine_from_config, pool
from logging.config import fileConfig
from configparser import ConfigParser

config = context.config

cherrypy_config_file = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                                                    '..', 'config', 'opmuse.ini')
cherrypy_config = ConfigParser()
cherrypy_config.read(cherrypy_config_file)

database_url = cherrypy_config['opmuse']['database.url'].strip("'\"")

config.set_main_option('sqlalchemy.url', database_url)

fileConfig(config.config_file_name)

from opmuse import *
from opmuse.database import Base
target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    engine = engine_from_config(
                config.get_section(config.config_ini_section),
                prefix='sqlalchemy.',
                poolclass=pool.NullPool)

    connection = engine.connect()
    context.configure(connection=connection,
                      target_metadata=target_metadata)

    try:
        with context.begin_transaction():
            context.run_migrations()
    finally:
        connection.close()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
