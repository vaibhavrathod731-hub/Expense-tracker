"""Shared repository row conversion and query helpers."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TypeVar

from smartspend.db.connection import atomic
from smartspend.db.errors import DatabaseIntegrityError, DatabaseOperationError

Record = TypeVar("Record")


@contextmanager
def database_operation() -> Iterator[None]:
    """Translate SQLite query errors to application-level database errors."""
    try:
        yield
    except sqlite3.IntegrityError as exc:
        raise DatabaseIntegrityError(f"Database constraint failed: {exc}") from exc
    except sqlite3.Error as exc:
        raise DatabaseOperationError(f"Database operation failed: {exc}") from exc


def fetch_one(
    connection: sqlite3.Connection,
    query: str,
    parameters: tuple[object, ...],
    converter: type[Record],
) -> Record | None:
    with database_operation():
        row = connection.execute(query, parameters).fetchone()
    return converter(**dict(row)) if row is not None else None


def fetch_all(
    connection: sqlite3.Connection,
    query: str,
    parameters: tuple[object, ...],
    converter: type[Record],
) -> list[Record]:
    with database_operation():
        rows = connection.execute(query, parameters).fetchall()
    return [converter(**dict(row)) for row in rows]


def write_and_fetch(
    connection: sqlite3.Connection,
    query: str,
    parameters: tuple[object, ...],
    fetch_query: str,
    converter: type[Record],
) -> Record:
    with atomic(connection):
        cursor = connection.execute(query, parameters)
        row = connection.execute(fetch_query, (cursor.lastrowid,)).fetchone()
    if row is None:
        raise DatabaseOperationError("Inserted record could not be retrieved.")
    return converter(**dict(row))
