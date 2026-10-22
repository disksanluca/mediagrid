"""Use the same engine and model metadata as the MediaGrid Core."""

from alembic import context

from apps.api import models  # noqa: F401
from apps.api.database import Base, engine

target_metadata = Base.metadata


def run_migrations_online() -> None:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()

