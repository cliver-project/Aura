"""Aura database migration CLI.

Usage:
    python -m aura.migrate upgrade [revision] [--sql]
    python -m aura.migrate downgrade <revision>
    python -m aura.migrate stamp [revision]
    python -m aura.migrate current
    python -m aura.migrate history
    python -m aura.migrate check

Every command accepts --url. The URL may use asyncpg, psycopg, or the plain
postgresql:// form; it is normalized for Alembic.
"""

from __future__ import annotations

import argparse
import sys

from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from aura import alembic as migrations
from aura.config import get_settings


async def ensure_current_revision(session: AsyncSession) -> None:
    """Fail fast when the application starts against an unmigrated database."""
    head = ScriptDirectory.from_config(migrations.make_config()).get_current_head()
    try:
        row = (await session.execute(text("select version_num from alembic_version"))).scalar_one_or_none()
    except Exception as exc:  # noqa: BLE001 - any read failure means "not migrated"
        raise RuntimeError("Database schema is not managed by Alembic. Run: make migrate") from exc
    if row != head:
        raise RuntimeError(f"Database schema is at revision {row or 'none'}, expected {head}. Run: make migrate")


def _target(database_url: str | None) -> str:
    url = database_url or get_settings().database_url
    return make_url(url).render_as_string(hide_password=True)


def _common_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    # SUPPRESS lets the main parser and a subparser both accept --url without
    # one overwriting the other with its default.
    parser.add_argument(
        "--url",
        default=argparse.SUPPRESS,
        help="Database URL. Defaults to the application settings.",
    )
    return parser


def build_parser() -> argparse.ArgumentParser:
    common = _common_parser()
    parser = argparse.ArgumentParser(
        description="Aura database migrations",
        parents=[common],
    )
    sub = parser.add_subparsers(dest="command", required=True)

    upgrade = sub.add_parser("upgrade", parents=[common], help="Upgrade to a revision")
    upgrade.add_argument("revision", nargs="?", default="head")
    upgrade.add_argument("--sql", action="store_true", help="Render SQL instead of executing")

    downgrade = sub.add_parser("downgrade", parents=[common], help="Downgrade to a revision")
    downgrade.add_argument("revision")
    downgrade.add_argument("--sql", action="store_true", help="Render SQL instead of executing")

    stamp = sub.add_parser("stamp", parents=[common], help="Record a revision without running it")
    stamp.add_argument("revision", nargs="?", default="head")

    sub.add_parser("current", parents=[common], help="Show the current revision")
    sub.add_parser("history", parents=[common], help="Show the revision history")
    sub.add_parser("check", parents=[common], help="Check models against the database")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    database_url = getattr(args, "url", None)
    print(f"[aura] database: {_target(database_url)}", file=sys.stderr)

    if args.command == "upgrade":
        migrations.upgrade(args.revision, database_url, sql=args.sql)
    elif args.command == "downgrade":
        migrations.downgrade(args.revision, database_url, sql=args.sql)
    elif args.command == "stamp":
        migrations.stamp(args.revision, database_url)
    elif args.command == "current":
        migrations.current(database_url)
    elif args.command == "history":
        migrations.history(database_url)
    elif args.command == "check":
        migrations.check(database_url)
    else:  # pragma: no cover - argparse enforces the choices
        raise SystemExit(f"Unknown command: {args.command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
