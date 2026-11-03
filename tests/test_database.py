import sqlite3

import pytest

from smartspend.db import atomic, initialize_database, open_connection
from smartspend.db.errors import (
    DatabaseConnectionError,
    DatabaseIntegrityError,
    DatabaseOperationError,
    DatabaseVersionError,
    RecordNotFoundError,
)
from smartspend.repositories.budgets import (
    create_budget,
    delete_budget,
    get_budget,
    list_budgets,
    update_budget,
)
from smartspend.repositories.categories import (
    create_category,
    delete_category,
    get_category,
    list_categories,
    update_category,
)
from smartspend.repositories.transactions import (
    create_transaction,
    delete_transaction,
    get_transaction,
    list_transactions,
    update_transaction,
)


def category_id(connection, name, category_type):
    category = next(
        category for category in list_categories(connection, category_type) if category.name == name
    )
    return category.id


def test_initialization_creates_schema_enables_foreign_keys_and_seeds_defaults(
    database_path,
):
    with open_connection(database_path) as connection:
        table_names = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = ?",
                ("table",),
            )
        }
        seeded_categories = list_categories(connection)

        assert {"categories", "transactions", "budgets"} <= table_names
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert len(seeded_categories) == 12
        assert all(category.is_default for category in seeded_categories)
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1


def test_initialization_is_idempotent_and_does_not_duplicate_defaults(database_path):
    initialize_database(database_path)
    initialize_database(database_path)

    with open_connection(database_path) as connection:
        defaults = [category for category in list_categories(connection) if category.is_default]
        assert len(defaults) == 12
        assert len({(category.name, category.category_type) for category in defaults}) == 12


def test_each_test_database_is_isolated(tmp_path):
    first_path = tmp_path / "first.sqlite3"
    second_path = tmp_path / "second.sqlite3"
    initialize_database(first_path)
    initialize_database(second_path)

    with open_connection(first_path) as first, open_connection(second_path) as second:
        created = create_category(first, "Personal", "expense")

        assert get_category(first, created.id) is not None
        assert get_category(second, created.id) is None


def test_category_crud_and_default_protection(db_connection):
    created = create_category(db_connection, "Pets", "expense")
    assert get_category(db_connection, created.id) == created

    updated = update_category(db_connection, created.id, "Pet care", "expense")
    assert updated.name == "Pet care"
    assert updated.category_type == "expense"
    assert updated.updated_at >= created.updated_at
    assert updated in list_categories(db_connection, "expense")

    delete_category(db_connection, created.id)
    assert get_category(db_connection, created.id) is None

    food_id = category_id(db_connection, "Food", "expense")
    with pytest.raises(DatabaseIntegrityError, match="Default categories"):
        delete_category(db_connection, food_id)
    with pytest.raises(DatabaseIntegrityError, match="Default categories"):
        update_category(db_connection, food_id, "Groceries", "expense")


def test_category_constraints_and_missing_records(db_connection):
    food_id = category_id(db_connection, "Food", "expense")
    with pytest.raises(DatabaseIntegrityError):
        create_category(db_connection, "Food", "expense")
    with pytest.raises(DatabaseIntegrityError):
        create_category(db_connection, "Invalid type", "transfer")
    with pytest.raises(RecordNotFoundError):
        update_category(db_connection, -1, "Missing", "expense")
    with pytest.raises(RecordNotFoundError):
        delete_category(db_connection, -1)

    create_transaction(
        db_connection,
        "2026-01-10",
        1250,
        "expense",
        food_id,
    )
    with pytest.raises(DatabaseIntegrityError):
        delete_category(db_connection, food_id)


def test_transaction_crud_uses_integer_paise_and_parameterized_values(db_connection):
    salary_id = category_id(db_connection, "Salary", "income")
    food_id = category_id(db_connection, "Food", "expense")
    description = "Lunch'); DROP TABLE transactions; --"

    created = create_transaction(
        db_connection,
        "2026-01-05",
        420000,
        "income",
        salary_id,
        description,
        "Bank transfer",
    )
    assert created.amount_paise == 420000
    assert get_transaction(db_connection, created.id) == created
    assert created.description == description

    updated = update_transaction(
        db_connection,
        created.id,
        "2026-01-06",
        2500,
        "expense",
        food_id,
        "Lunch",
        "Card",
    )
    assert updated.transaction_date == "2026-01-06"
    assert updated.amount_paise == 2500
    assert updated.transaction_type == "expense"
    assert updated in list_transactions(db_connection)
    assert list_transactions(db_connection, limit=1) == [updated]

    delete_transaction(db_connection, updated.id)
    assert get_transaction(db_connection, updated.id) is None


@pytest.mark.parametrize(
    ("transaction_date", "amount_paise", "transaction_type", "category_name", "category_type"),
    [
        ("2026-02-30", 100, "expense", "Food", "expense"),
        ("2026-01-01", 0, "expense", "Food", "expense"),
        ("2026-01-01", -1, "expense", "Food", "expense"),
        ("2026-01-01", 100.5, "expense", "Food", "expense"),
        ("2026-01-01", 100, "income", "Food", "expense"),
        ("2026-01-01", 100, "expense", "Salary", "income"),
        ("2026-01-01", 100, "expense", "Missing", "expense"),
    ],
)
def test_transaction_constraints_reject_invalid_values(
    db_connection,
    transaction_date,
    amount_paise,
    transaction_type,
    category_name,
    category_type,
):
    if category_name == "Missing":
        category_id_value = -1
    else:
        category_id_value = category_id(db_connection, category_name, category_type)

    with pytest.raises(DatabaseIntegrityError):
        create_transaction(
            db_connection,
            transaction_date,
            amount_paise,
            transaction_type,
            category_id_value,
        )

    assert list_transactions(db_connection) == []


def test_transaction_missing_records_and_invalid_limit(db_connection):
    with pytest.raises(RecordNotFoundError):
        update_transaction(db_connection, -1, "2026-01-01", 100, "expense", -1)
    with pytest.raises(RecordNotFoundError):
        delete_transaction(db_connection, -1)
    with pytest.raises(ValueError, match="positive"):
        list_transactions(db_connection, limit=0)


def test_budget_crud_and_monthly_uniqueness(db_connection):
    food_id = category_id(db_connection, "Food", "expense")

    overall = create_budget(db_connection, "2026-01-01", 500000)
    category_budget = create_budget(db_connection, "2026-01-01", 100000, food_id)
    assert get_budget(db_connection, overall.id) == overall
    assert {budget.id for budget in list_budgets(db_connection, "2026-01-01")} == {
        overall.id,
        category_budget.id,
    }

    updated = update_budget(db_connection, category_budget.id, "2026-02-01", 125000, food_id)
    assert updated.month == "2026-02-01"
    assert updated.amount_paise == 125000
    assert updated in list_budgets(db_connection, "2026-02-01")

    delete_budget(db_connection, updated.id)
    assert get_budget(db_connection, updated.id) is None

    with pytest.raises(DatabaseIntegrityError):
        create_budget(db_connection, "2026-01-01", 600000)
    with pytest.raises(RecordNotFoundError):
        update_budget(db_connection, -1, "2026-01-01", 100)
    with pytest.raises(RecordNotFoundError):
        delete_budget(db_connection, -1)


def test_budget_constraints_reject_invalid_month_amount_category_and_duplicates(
    db_connection,
):
    food_id = category_id(db_connection, "Food", "expense")
    salary_id = category_id(db_connection, "Salary", "income")
    create_budget(db_connection, "2026-01-01", 1000, food_id)

    invalid_budgets = [
        ("2026-01-15", 1000, None),
        ("2026-02-01", 0, None),
        ("2026-02-01", 100.5, None),
        ("2026-02-01", 1000, salary_id),
        ("2026-01-01", 2000, food_id),
    ]
    for month, amount_paise, category in invalid_budgets:
        with pytest.raises(DatabaseIntegrityError):
            create_budget(db_connection, month, amount_paise, category)

    assert len(list_budgets(db_connection)) == 1


def test_budget_category_foreign_key_prevents_category_deletion(db_connection):
    food_id = category_id(db_connection, "Food", "expense")
    create_budget(db_connection, "2026-01-01", 10000, food_id)

    with pytest.raises(DatabaseIntegrityError):
        delete_category(db_connection, food_id)


def test_budget_categories_must_remain_expense_categories(db_connection):
    custom_category = create_category(db_connection, "Pet care", "expense")
    create_budget(db_connection, "2026-01-01", 10000, custom_category.id)

    with pytest.raises(DatabaseIntegrityError, match="remain expense"):
        update_category(db_connection, custom_category.id, "Pet care", "income")


def test_database_constraints_protect_default_categories_from_direct_sql(db_connection):
    food_id = category_id(db_connection, "Food", "expense")

    with pytest.raises(DatabaseIntegrityError, match="default categories cannot be changed"):
        with atomic(db_connection):
            db_connection.execute(
                "UPDATE categories SET name = ? WHERE id = ?",
                ("Groceries", food_id),
            )
    with pytest.raises(DatabaseIntegrityError, match="default categories cannot be deleted"):
        with atomic(db_connection):
            db_connection.execute("DELETE FROM categories WHERE id = ?", (food_id,))


def test_atomic_rolls_back_nested_repository_operations(db_connection):
    with pytest.raises(RuntimeError, match="abort outer transaction"):
        with atomic(db_connection):
            created = create_category(db_connection, "Temporary", "expense")
            assert get_category(db_connection, created.id) is not None
            raise RuntimeError("abort outer transaction")

    assert all(category.name != "Temporary" for category in list_categories(db_connection))


def test_database_errors_are_translated_and_connections_are_closed(tmp_path):
    with pytest.raises(DatabaseConnectionError):
        with open_connection(tmp_path):
            pass

    database_path = tmp_path / "broken.sqlite3"
    initialize_database(database_path)
    with open_connection(database_path) as connection:
        connection.execute("DROP TABLE transactions")
        connection.commit()
        with pytest.raises(DatabaseOperationError):
            list_transactions(connection)


def test_newer_schema_version_is_rejected_without_creating_tables(tmp_path):
    database_path = tmp_path / "future.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA user_version = 99")

    with pytest.raises(DatabaseVersionError):
        initialize_database(database_path)

    with sqlite3.connect(database_path) as connection:
        table_count = connection.execute(
            "SELECT count(*) FROM sqlite_master WHERE type = ?",
            ("table",),
        ).fetchone()[0]
        assert table_count == 0
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 99
