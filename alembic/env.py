import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# 1. Import ORM Declarative Base and all application models
from app.core.database import Base
import app.models  # Ensures all models (auth, lead, telecaller, hr, bdm, ops, audit) register on Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# 2. Extract database URL from app settings or environment
db_url = os.getenv("DATABASE_URL")
if not db_url:
    from app.core.config import settings
    db_url = settings.ASYNC_DATABASE_URL

# Normalize dialect prefix for asyncpg
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)

# Clean query arguments for asyncpg compatibility
if "sslmode=" in db_url:
    db_url = db_url.replace("sslmode=require", "ssl=require")

if "&channel_binding=" in db_url:
    db_url = db_url.split("&channel_binding=")[0]

config.set_main_option("sqlalchemy.url", db_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode using AsyncEngine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()