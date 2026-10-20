"""Opt-in database integration tests for startup seeding.

Set AURA_TEST_DATABASE_URL to a PostgreSQL admin URL to run these. They create
and drop their own scratch database and never touch the application database.
"""

from __future__ import annotations

import asyncio
import os
import uuid

import psycopg
import pytest
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from aura import alembic as migrations
from aura.models import AgentProfile
from aura.services.seed import (
    apply_knowledge_defaults,
    seed_default_agents,
    seed_default_mcp_servers,
)

pytestmark = pytest.mark.skipif(
    not os.environ.get("AURA_TEST_DATABASE_URL"),
    reason="Set AURA_TEST_DATABASE_URL to run scratch-database seed tests",
)


def _create_scratch() -> tuple[str, str, str]:
    admin_url = make_url(os.environ["AURA_TEST_DATABASE_URL"]).set(drivername="postgresql")
    admin_dsn = admin_url.render_as_string(hide_password=False)
    database = f"aura_seed_test_{uuid.uuid4().hex[:10]}"
    test_url = admin_url.set(database=database).render_as_string(hide_password=False)
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        connection.execute(f'CREATE DATABASE "{database}"')
    migrations.upgrade("head", test_url)
    return admin_dsn, database, test_url


def _drop_scratch(admin_dsn: str, database: str) -> None:
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        connection.execute(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)')


def test_seed_and_knowledge_defaults_are_idempotent() -> None:
    admin_dsn, database, sync_url = _create_scratch()
    async_url = make_url(sync_url).set(drivername="postgresql+asyncpg").render_as_string(
        hide_password=False
    )
    try:

        async def scenario() -> None:
            engine = create_async_engine(async_url)
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            try:
                async with session_factory() as session:
                    server = await seed_default_mcp_servers(session)
                    assert server is not None
                    assert server.transport == "sse"
                    assert server.url == "{{ragflow_mcp_url}}"
                    assert server.headers == {"api_key": "{{ragflow_api_key}}"}

                    await seed_default_agents(session)
                    await apply_knowledge_defaults(session)

                    ba = (
                        await session.execute(
                            select(AgentProfile).where(AgentProfile.role_key == "ba")
                        )
                    ).scalar_one()
                    assert "knowledge-base" in ba.skill_names
                    assert server.id in ba.mcp_server_ids

                    # The one-time marker means user removals are not re-added.
                    ba.skill_names = [
                        name for name in ba.skill_names if name != "knowledge-base"
                    ]
                    ba.mcp_server_ids = []
                    await session.commit()
                    await apply_knowledge_defaults(session)
                    await session.refresh(ba)
                    assert "knowledge-base" not in ba.skill_names
                    assert server.id not in ba.mcp_server_ids
            finally:
                await engine.dispose()

        asyncio.run(scenario())
    finally:
        _drop_scratch(admin_dsn, database)
