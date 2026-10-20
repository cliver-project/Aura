"""Schema helpers for tests and throwaway databases only.

Production schema changes belong in Alembic migrations.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine

from aura.db.base import Base


def _register_models() -> None:
    from aura import models  # noqa: F401


async def create_all(engine: AsyncEngine) -> None:
    _register_models()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def drop_all(engine: AsyncEngine) -> None:
    _register_models()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
