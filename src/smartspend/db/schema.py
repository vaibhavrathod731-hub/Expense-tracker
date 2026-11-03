"""SQLite schema creation and default category seeding."""

from __future__ import annotations

from pathlib import Path

from smartspend.config import ensure_data_directory, load_settings
from smartspend.db.connection import DatabasePath, atomic, open_connection
from smartspend.db.errors import DatabaseConnectionError, DatabaseVersionError

SCHEMA_VERSION = 1

DEFAULT_CATEGORIES = (
    ("Food", "expense"),
    ("Transportation", "expense"),
    ("Shopping", "expense"),
    ("Education", "expense"),
    ("Healthcare", "expense"),
    ("Entertainment", "expense"),
    ("Rent", "expense"),
    ("Utilities", "expense"),
    ("Other", "expense"),
    ("Salary", "income"),
    ("Freelancing", "income"),
    ("Other", "income"),
)

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL CHECK (length(trim(name)) > 0),
        category_type TEXT NOT NULL CHECK (category_type IN ('income', 'expense')),
        is_default INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0, 1)),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (name, category_type),
        UNIQUE (id, category_type)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY,
        transaction_date TEXT NOT NULL
            CHECK (
                length(transaction_date) = 10
                AND date(transaction_date) IS NOT NULL
                AND date(transaction_date) = transaction_date
            ),
        amount_paise INTEGER NOT NULL
            CHECK (typeof(amount_paise) = 'integer' AND amount_paise > 0),
        transaction_type TEXT NOT NULL CHECK (transaction_type IN ('income', 'expense')),
        category_id INTEGER NOT NULL,
        description TEXT,
        payment_method TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (category_id, transaction_type)
            REFERENCES categories (id, category_type)
            ON UPDATE RESTRICT
            ON DELETE RESTRICT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS budgets (
        id INTEGER PRIMARY KEY,
        month TEXT NOT NULL
            CHECK (
                length(month) = 10
                AND strftime('%Y-%m-01', month) IS NOT NULL
                AND month = strftime('%Y-%m-01', month)
            ),
        amount_paise INTEGER NOT NULL
            CHECK (typeof(amount_paise) = 'integer' AND amount_paise > 0),
        category_id INTEGER,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (category_id) REFERENCES categories (id)
            ON UPDATE RESTRICT
            ON DELETE RESTRICT
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_budgets_overall_month
        ON budgets (month)
        WHERE category_id IS NULL
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_budgets_category_month
        ON budgets (month, category_id)
        WHERE category_id IS NOT NULL
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_transactions_date
        ON transactions (transaction_date)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_transactions_category_date
        ON transactions (category_id, transaction_date)
    """,
    """
    CREATE TRIGGER IF NOT EXISTS validate_budget_category_insert
    BEFORE INSERT ON budgets
    WHEN NEW.category_id IS NOT NULL
         AND NOT EXISTS (
             SELECT 1 FROM categories
             WHERE id = NEW.category_id AND category_type = 'expense'
         )
    BEGIN
        SELECT RAISE(ABORT, 'category budgets require an expense category');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS validate_budget_category_update
    BEFORE UPDATE OF category_id ON budgets
    WHEN NEW.category_id IS NOT NULL
         AND NOT EXISTS (
             SELECT 1 FROM categories
             WHERE id = NEW.category_id AND category_type = 'expense'
         )
    BEGIN
        SELECT RAISE(ABORT, 'category budgets require an expense category');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS validate_budget_category_type_update
    BEFORE UPDATE OF category_type ON categories
    WHEN NEW.category_type <> 'expense'
         AND EXISTS (SELECT 1 FROM budgets WHERE category_id = OLD.id)
    BEGIN
        SELECT RAISE(ABORT, 'budget categories must remain expense categories');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS prevent_default_category_update
    BEFORE UPDATE OF name, category_type ON categories
    WHEN OLD.is_default = 1
    BEGIN
        SELECT RAISE(ABORT, 'default categories cannot be changed');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS prevent_default_category_delete
    BEFORE DELETE ON categories
    WHEN OLD.is_default = 1
    BEGIN
        SELECT RAISE(ABORT, 'default categories cannot be deleted');
    END
    """,
)


def _resolve_database_path(database_path: DatabasePath | None) -> DatabasePath:
    if database_path is not None:
        return database_path

    settings = load_settings()
    ensure_data_directory(settings)
    return settings.database_path


def initialize_database(database_path: DatabasePath | None = None) -> Path | str:
    """Create the schema and seed default categories without duplicating them."""
    resolved_path = _resolve_database_path(database_path)
    if str(resolved_path) == ":memory:":
        raise ValueError("Use a temporary database file to initialize an isolated database.")
    try:
        Path(resolved_path).expanduser().resolve().parent.mkdir(
            parents=True,
            exist_ok=True,
        )
    except OSError as exc:
        raise DatabaseConnectionError(f"Unable to create the database directory: {exc}") from exc

    with open_connection(resolved_path) as connection:
        with atomic(connection):
            current_version = connection.execute("PRAGMA user_version").fetchone()[0]
            if current_version > SCHEMA_VERSION:
                raise DatabaseVersionError(
                    f"Database schema version {current_version} is newer than "
                    f"supported version {SCHEMA_VERSION}."
                )

            for statement in SCHEMA_STATEMENTS:
                connection.execute(statement)

            connection.executemany(
                """
                INSERT INTO categories (name, category_type, is_default)
                VALUES (?, ?, 1)
                ON CONFLICT (name, category_type) DO NOTHING
                """,
                DEFAULT_CATEGORIES,
            )
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    return resolved_path
