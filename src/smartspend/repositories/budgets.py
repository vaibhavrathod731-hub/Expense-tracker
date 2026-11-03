"""Monthly overall and category budget CRUD operations."""

import sqlite3

from smartspend.db.connection import atomic
from smartspend.db.errors import RecordNotFoundError
from smartspend.db.models import Budget
from smartspend.repositories._shared import fetch_all, fetch_one, write_and_fetch


def create_budget(
    connection: sqlite3.Connection,
    month: str,
    amount_paise: int,
    category_id: int | None = None,
) -> Budget:
    """Create a monthly overall budget or an expense-category budget."""
    return write_and_fetch(
        connection,
        """
        INSERT INTO budgets (month, amount_paise, category_id)
        VALUES (?, ?, ?)
        """,
        (month, amount_paise, category_id),
        "SELECT * FROM budgets WHERE id = ?",
        Budget,
    )


def get_budget(connection: sqlite3.Connection, budget_id: int) -> Budget | None:
    """Return one budget, or None when its ID does not exist."""
    return fetch_one(
        connection,
        "SELECT * FROM budgets WHERE id = ?",
        (budget_id,),
        Budget,
    )


def list_budgets(connection: sqlite3.Connection, month: str | None = None) -> list[Budget]:
    """Return budgets by month, optionally filtering to one YYYY-MM-01 month."""
    if month is None:
        query = "SELECT * FROM budgets ORDER BY month DESC, category_id"
        parameters: tuple[object, ...] = ()
    else:
        query = "SELECT * FROM budgets WHERE month = ? ORDER BY category_id"
        parameters = (month,)
    return fetch_all(connection, query, parameters, Budget)


def update_budget(
    connection: sqlite3.Connection,
    budget_id: int,
    month: str,
    amount_paise: int,
    category_id: int | None = None,
) -> Budget:
    """Update a monthly budget and its modification timestamp."""
    with atomic(connection):
        cursor = connection.execute(
            """
            UPDATE budgets
            SET month = ?, amount_paise = ?, category_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (month, amount_paise, category_id, budget_id),
        )
        if cursor.rowcount == 0:
            raise RecordNotFoundError(f"Budget {budget_id} does not exist.")
        row = connection.execute(
            "SELECT * FROM budgets WHERE id = ?",
            (budget_id,),
        ).fetchone()
    return Budget(**dict(row))


def delete_budget(connection: sqlite3.Connection, budget_id: int) -> None:
    """Delete a budget by ID."""
    with atomic(connection):
        cursor = connection.execute("DELETE FROM budgets WHERE id = ?", (budget_id,))
        if cursor.rowcount == 0:
            raise RecordNotFoundError(f"Budget {budget_id} does not exist.")


__all__ = [
    "create_budget",
    "delete_budget",
    "get_budget",
    "list_budgets",
    "update_budget",
]
