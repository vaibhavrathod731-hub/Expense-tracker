"""SQLite connection lifecycle and transaction helpers."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from itertools import count
from pathlib import Path
from typing import TypeAlias

from smartspend.db.errors import (
    DatabaseConnectionError,
    DatabaseIntegrityError,
    DatabaseOperationError,
)

DatabasePath: TypeAlias = str | Path
_SAVEPOINT_IDS = count()


@contextmanager
def open_connection(database_path: DatabasePath) -> Iterator[sqlite3.Connection]:
    """Open and close a configured SQLite connection."""
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(database_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
    except sqlite3.Error as exc:
        if connection is not None:
            connection.close()
        raise DatabaseConnectionError(f"Unable to open SQLite database: {exc}") from exc

    if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        connection.close()
        raise DatabaseConnectionError("SQLite foreign key enforcement is unavailable.")

    try:
        yield connection
    finally:
        connection.close()


@contextmanager
def atomic(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Run database operations atomically and translate SQLite failures."""
    savepoint = None
    try:
        if connection.in_transaction:
            savepoint = f"smartspend_{id(connection)}_{next(_SAVEPOINT_IDS)}"
            connection.execute(f"SAVEPOINT {savepoint}")
        else:
            connection.execute("BEGIN")
        try:
            yield connection
        except BaseException as exc:
            if savepoint is None:
                connection.rollback()
            else:
                connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                connection.execute(f"RELEASE SAVEPOINT {savepoint}")
            if isinstance(exc, sqlite3.IntegrityError):
                raise DatabaseIntegrityError(f"Database constraint failed: {exc}") from exc
            if isinstance(exc, sqlite3.Error):
                raise DatabaseOperationError(f"Database operation failed: {exc}") from exc
            raise
        else:
            if savepoint is None:
                connection.commit()
            else:
                connection.execute(f"RELEASE SAVEPOINT {savepoint}")
    except sqlite3.IntegrityError as exc:
        raise DatabaseIntegrityError(f"Database constraint failed: {exc}") from exc
    except sqlite3.Error as exc:
        if connection.in_transaction:
            connection.rollback()
        raise DatabaseOperationError(f"Database operation failed: {exc}") from exc
