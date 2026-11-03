"""Transaction CRUD operations using integer paise."""

import sqlite3

from smartspend.db.connection import atomic
from smartspend.db.errors import RecordNotFoundError
from smartspend.db.models import Transaction
from smartspend.repositories._shared import fetch_all, fetch_one, write_and_fetch


def create_transaction(
    connection: sqlite3.Connection,
    transaction_date: str,
    amount_paise: int,
    transaction_type: str,
    category_id: int,
    description: str | None = None,
    payment_method: str | None = None,
) -> Transaction:
    """Insert a transaction; amount_paise is an integer number of paise."""
    return write_and_fetch(
        connection,
        """
        INSERT INTO transactions (
            transaction_date, amount_paise, transaction_type,
            category_id, description, payment_method
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            transaction_date,
            amount_paise,
            transaction_type,
            category_id,
            description,
            payment_method,
        ),
        "SELECT * FROM transactions WHERE id = ?",
        Transaction,
    )


def get_transaction(
    connection: sqlite3.Connection,
    transaction_id: int,
) -> Transaction | None:
    """Return one transaction, or None when its ID does not exist."""
    return fetch_one(
        connection,
        "SELECT * FROM transactions WHERE id = ?",
        (transaction_id,),
        Transaction,
    )


def list_transactions(
    connection: sqlite3.Connection,
    limit: int | None = None,
) -> list[Transaction]:
    """Return transactions newest first, optionally limiting the result count."""
    query = "SELECT * FROM transactions ORDER BY transaction_date DESC, id DESC"
    parameters: tuple[object, ...] = ()
    if limit is not None:
        if limit < 1:
            raise ValueError("limit must be a positive integer.")
        query += " LIMIT ?"
        parameters = (limit,)
    return fetch_all(connection, query, parameters, Transaction)


def update_transaction(
    connection: sqlite3.Connection,
    transaction_id: int,
    transaction_date: str,
    amount_paise: int,
    transaction_type: str,
    category_id: int,
    description: str | None = None,
    payment_method: str | None = None,
) -> Transaction:
    """Update a transaction and its modification timestamp."""
    with atomic(connection):
        cursor = connection.execute(
            """
            UPDATE transactions
            SET transaction_date = ?, amount_paise = ?, transaction_type = ?,
                category_id = ?, description = ?, payment_method = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                transaction_date,
                amount_paise,
                transaction_type,
                category_id,
                description,
                payment_method,
                transaction_id,
            ),
        )
        if cursor.rowcount == 0:
            raise RecordNotFoundError(f"Transaction {transaction_id} does not exist.")
        row = connection.execute(
            "SELECT * FROM transactions WHERE id = ?",
            (transaction_id,),
        ).fetchone()
    return Transaction(**dict(row))


def delete_transaction(connection: sqlite3.Connection, transaction_id: int) -> None:
    """Delete a transaction by ID."""
    with atomic(connection):
        cursor = connection.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
        if cursor.rowcount == 0:
            raise RecordNotFoundError(f"Transaction {transaction_id} does not exist.")


__all__ = [
    "create_transaction",
    "delete_transaction",
    "get_transaction",
    "list_transactions",
    "update_transaction",
]
