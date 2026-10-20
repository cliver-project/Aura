"""Declarative base and deterministic constraint/index naming."""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# These conventions reproduce the names PostgreSQL already generated for the
# existing Aura schema. Keeping them stable lets Alembic compare the live
# database with the models without proposing renames.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}


class Base(DeclarativeBase):
    """All entities subclass this base. Alembic's target_metadata is Base.metadata."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
