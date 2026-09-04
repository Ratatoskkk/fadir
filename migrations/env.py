from __future__ import annotations

import os

from alembic import context
from alembic.ddl.postgresql import PostgresqlImpl
from sqlalchemy import Table, Text, engine_from_config, pool

from app.models import Base


config = context.config
target_metadata = Base.metadata


class FadirPostgresqlImpl(PostgresqlImpl):
    __dialect__ = "postgresql"

    # Alembic 1.14+ exposes this dialect hook for the version table definition.
    def version_table_impl(
        self,
        *,
        version_table: str,
        version_table_schema: str | None,
        version_table_pk: bool,
        **kw,
    ) -> Table:
        table = super().version_table_impl(
            version_table=version_table,
            version_table_schema=version_table_schema,
            version_table_pk=version_table_pk,
            **kw,
        )
        table.c.version_num.type = Text()
        return table


def _database_url() -> str:
    database_url = os.environ.get("FADIR_DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "FADIR_DATABASE_URL is required for every migration command"
        )
    return database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    settings = config.get_section(config.config_ini_section) or {}
    settings["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        settings,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
