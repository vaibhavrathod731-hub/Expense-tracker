"""Category CRUD operations."""

import sqlite3

from smartspend.db.connection import atomic
from smartspend.db.errors import DatabaseIntegrityError, RecordNotFoundError
from smartspend.db.models import Category
from smartspend.repositories._shared import (
    fetch_all,
    fetch_one,
    write_and_fetch,
)


def create_category(
    connection: sqlite3.Connection,
    name: str,
    category_type: str,
) -> Category:
    """Create a user-defined category."""
    return write_and_fetch(
        connection,
        """
        INSERT INTO categories (name, category_type)
        VALUES (?, ?)
        """,
        (name, category_type),
        "SELECT * FROM categories WHERE id = ?",
        Category,
    )


def get_category(connection: sqlite3.Connection, category_id: int) -> Category | None:
    """Return one category, or None when its ID does not exist."""
    return fetch_one(
        connection,
        "SELECT * FROM categories WHERE id = ?",
        (category_id,),
        Category,
    )


def list_categories(
    connection: sqlite3.Connection,
    category_type: str | None = None,
) -> list[Category]:
    """Return categories ordered by type and name, optionally filtered by type."""
    if category_type is None:
        query = "SELECT * FROM categories ORDER BY category_type, name"
        parameters: tuple[object, ...] = ()
    else:
        query = "SELECT * FROM categories WHERE category_type = ? ORDER BY name"
        parameters = (category_type,)
    return fetch_all(connection, query, parameters, Category)


def update_category(
    connection: sqlite3.Connection,
    category_id: int,
    name: str,
    category_type: str,
) -> Category:
    """Update a category, rejecting changes that violate dependent records."""
    with atomic(connection):
        existing = connection.execute(
            "SELECT is_default FROM categories WHERE id = ?",
            (category_id,),
        ).fetchone()
        if existing is None:
            raise RecordNotFoundError(f"Category {category_id} does not exist.")
        if existing["is_default"]:
            raise DatabaseIntegrityError("Default categories cannot be changed.")

        connection.execute(
            """
            UPDATE categories
            SET name = ?, category_type = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (name, category_type, category_id),
        )
        row = connection.execute(
            "SELECT * FROM categories WHERE id = ?",
            (category_id,),
        ).fetchone()
    return Category(**dict(row))


def delete_category(connection: sqlite3.Connection, category_id: int) -> None:
    """Delete an unused user category; default or referenced categories are protected."""
    with atomic(connection):
        row = connection.execute(
            "SELECT is_default FROM categories WHERE id = ?",
            (category_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"Category {category_id} does not exist.")
        if row["is_default"]:
            raise DatabaseIntegrityError("Default categories cannot be deleted.")

        connection.execute("DELETE FROM categories WHERE id = ?", (category_id,))


__all__ = [
    "create_category",
    "delete_category",
    "get_category",
    "list_categories",
    "update_category",
]
