from __future__ import annotations
import asyncio
import os
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from alembic import context

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    url = os.environ["DATABASE_URL"]
    engine = create_async_engine(url, poolclass=NullPool)
    async with engine.connect() as conn:
        await conn.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online():
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    raise RuntimeError("Offline mode not supported — set DATABASE_URL and run online")
else:
    run_migrations_online()
