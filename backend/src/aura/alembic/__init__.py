"""Programmatic Alembic entry points.

The script location is pinned to this package so migrations work regardless of
the caller's working directory. Database URLs are passed through
``config.attributes`` rather than ``Config.set_main_option``: ConfigParser
interpolates ``%`` characters, which can corrupt URL-encoded passwords.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

_SCRIPT_LOCATION = Path(__file__).resolve().parent


def sync_url(url: str) -> str:
    """Return a psycopg URL for Alembic; leave non-PostgreSQL URLs alone."""
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql":
        return url
    return parsed.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)


def make_config(database_url: str | None = None) -> Config:
    config = Config()
    config.set_main_option("script_location", str(_SCRIPT_LOCATION))
    if database_url:
        config.attributes["database_url"] = sync_url(database_url)
    return config


def upgrade(revision: str = "head", database_url: str | None = None, sql: bool = False) -> None:
    command.upgrade(make_config(database_url), revision, sql=sql)


def downgrade(revision: str, database_url: str | None = None, sql: bool = False) -> None:
    command.downgrade(make_config(database_url), revision, sql=sql)


def stamp(revision: str = "head", database_url: str | None = None) -> None:
    command.stamp(make_config(database_url), revision)


def current(database_url: str | None = None) -> None:
    command.current(make_config(database_url), verbose=True)


def history(database_url: str | None = None) -> None:
    command.history(make_config(database_url), verbose=True)


def check(database_url: str | None = None) -> None:
    command.check(make_config(database_url))


def run_migrations_online(database_url: str | None = None) -> None:
    upgrade("head", database_url)


def run_migrations_offline(database_url: str | None = None) -> None:
    upgrade("head", database_url, sql=True)
