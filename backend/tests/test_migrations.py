"""Migration tests.

The offline test always runs and catches a missing env.py dispatch. The
scratch-database test is opt-in via AURA_TEST_DATABASE_URL and never touches
the application database.
"""

from __future__ import annotations

import contextlib
import io
import os
import uuid

import psycopg
import pytest
from alembic import command
from sqlalchemy.engine import make_url

from aura import alembic as migrations


def test_offline_upgrade_renders_all_tables() -> None:
    config = migrations.make_config("postgresql+asyncpg://aura:secret@localhost:5432/aura")
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        command.upgrade(config, "head", sql=True)
    sql = output.getvalue()

    for table in (
        "projects",
        "requirements",
        "requirement_versions",
        "artifacts",
        "agent_profiles",
        "pipeline_runs",
        "stage_runs",
        "agent_runs",
        "agent_events",
        "skills",
        "mcp_servers",
        "app_settings",
    ):
        assert f"CREATE TABLE {table}" in sql
    assert "CREATE INDEX ix_requirements_project_id" in sql
    assert "uq_requirement_key" in sql
    assert "ON DELETE CASCADE" in sql
    assert "JSON" in sql
    assert "alembic_version" in sql
    assert "env JSON NOT NULL" in sql
    assert "ragflow_dataset_ids JSON NOT NULL" in sql
    assert "model_usage JSON NOT NULL" in sql


@pytest.mark.skipif(
    not os.environ.get("AURA_TEST_DATABASE_URL"),
    reason="Set AURA_TEST_DATABASE_URL to run the scratch-database migration test",
)
def test_scratch_database_upgrade_downgrade() -> None:
    admin_url = make_url(os.environ["AURA_TEST_DATABASE_URL"]).set(drivername="postgresql")
    admin_dsn = admin_url.render_as_string(hide_password=False)
    database = f"aura_migration_test_{uuid.uuid4().hex[:10]}"
    test_url = admin_url.set(database=database).render_as_string(hide_password=False)

    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        connection.execute(f'CREATE DATABASE "{database}"')

    try:
        migrations.upgrade("head", test_url)
        migrations.check(test_url)

        with psycopg.connect(test_url) as connection:
            tables = {
                row[0] for row in connection.execute("select tablename from pg_tables where schemaname = 'public'")
            }
        assert "projects" in tables
        assert "agent_events" in tables
        assert "alembic_version" in tables

        migrations.downgrade("base", test_url)
        with psycopg.connect(test_url) as connection:
            remaining = {
                row[0] for row in connection.execute("select tablename from pg_tables where schemaname = 'public'")
            }
        assert remaining == {"alembic_version"}
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as connection:
            connection.execute(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)')
