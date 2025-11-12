import os
import sys
from pathlib import Path

from alembic import context as alembic_context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from register_your_data_api.auth.fga.fga_provider_db import (  # noqa: F401, E402
    FineGrainedAuthorisationDbModel,
    SuperAdminUserDbModel,
)

config = alembic_context.config

target_metadata = SQLModel.metadata


def get_db_connection_string_from_env() -> str:
    load_dotenv()
    url = os.getenv("FGA_PROVIDER_CONNECTION_STRING")
    if url is None:
        raise RuntimeError("Set the DB connection string environment variable FGA_PROVIDER_CONNECTION_STRING")
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    db_conn_str = get_db_connection_string_from_env()

    alembic_context.configure(
        url=db_conn_str,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with alembic_context.begin_transaction():
        alembic_context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    config.set_main_option("sqlalchemy.url", get_db_connection_string_from_env())

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        alembic_context.configure(connection=connection, target_metadata=target_metadata)

        with alembic_context.begin_transaction():
            alembic_context.run_migrations()


# if not alembic_context.config.attributes.get("is_test_mode", False):
if alembic_context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
