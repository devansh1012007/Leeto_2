"""Alembic env: runs raw SQL migrations from versions/ (expand/contract only)."""

from alembic import context

config = context.config
target_metadata = None  # raw SQL migrations; no autogenerate


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    import sqlalchemy
    from alembic.runtime.environment import EnvironmentContext  # noqa: F401

    from core.config import get_settings

    url = config.get_main_option("sqlalchemy.url")
    if not url or url.startswith("driver://"):
        url = get_settings().dsn()
    engine = sqlalchemy.create_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
