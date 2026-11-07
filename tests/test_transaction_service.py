from datetime import date, datetime

import pytest

from smartspend.db.errors import RecordNotFoundError
from smartspend.repositories.categories import list_categories
from smartspend.repositories.transactions import get_transaction
from smartspend.services.transactions import (
    TransactionValidationError,
    create_transaction,
    delete_transaction,
    format_paise_as_rupees,
    list_transaction_history,
    rupees_to_paise,
    update_transaction,
)


def category_id(connection, name, category_type):
    return next(
        category.id
        for category in list_categories(connection, category_type)
        if category.name == name
    )


def test_add_income_converts_rupees_to_integer_paise(db_connection):
    salary_id = category_id(db_connection, "Salary", "income")

    transaction = create_transaction(
        db_connection,
        date(2026, 3, 5),
        "42000.50",
        "income",
        salary_id,
        "Bank transfer",
        "Monthly salary",
    )

    assert transaction.amount_paise == 4_200_050
    assert transaction.transaction_type == "income"
    assert transaction.transaction_date == "2026-03-05"
    assert transaction.description == "Monthly salary"


def test_add_expense_converts_rupees_and_normalizes_optional_description(db_connection):
    food_id = category_id(db_connection, "Food", "expense")

    transaction = create_transaction(
        db_connection,
        "2026-03-07",
        1250,
        "expense",
        food_id,
        "UPI",
        "  Groceries  ",
    )

    assert transaction.amount_paise == 125_000
    assert transaction.transaction_type == "expense"
    assert transaction.description == "Groceries"


def test_edit_transaction_persists_updated_fields(db_connection):
    salary_id = category_id(db_connection, "Salary", "income")
    food_id = category_id(db_connection, "Food", "expense")
    original = create_transaction(
        db_connection,
        "2026-01-03",
        "1200.00",
        "income",
        salary_id,
        "Bank transfer",
        "Pay",
    )

    updated = update_transaction(
        db_connection,
        original.id,
        "2026-01-04",
        "125.75",
        "expense",
        food_id,
        "UPI",
        "Lunch",
    )

    assert updated.id == original.id
    assert updated.transaction_date == "2026-01-04"
    assert updated.amount_paise == 12_575
    assert updated.transaction_type == "expense"
    assert updated.category_id == food_id
    assert get_transaction(db_connection, original.id) == updated


def test_delete_transaction_persists_and_reports_missing_records(db_connection):
    food_id = category_id(db_connection, "Food", "expense")
    transaction = create_transaction(
        db_connection,
        "2026-01-03",
        "80",
        "expense",
        food_id,
        "Cash",
    )

    delete_transaction(db_connection, transaction.id)

    assert get_transaction(db_connection, transaction.id) is None
    with pytest.raises(RecordNotFoundError):
        delete_transaction(db_connection, transaction.id)


@pytest.mark.parametrize(
    "amount",
    [
        "",
        "not money",
        "0",
        "-1",
        "1.001",
        "NaN",
        "Infinity",
        "999999999999999999999999999999999999",
        True,
    ],
)
def test_invalid_amounts_are_rejected(amount):
    with pytest.raises(TransactionValidationError):
        rupees_to_paise(amount)


def test_valid_amount_conversion_and_indian_formatting():
    assert rupees_to_paise("1.20") == 120
    assert rupees_to_paise("0.01") == 1
    assert format_paise_as_rupees(123_456_789) == "₹12,34,567.89"
    assert format_paise_as_rupees(10) == "₹0.10"
    assert format_paise_as_rupees(-123_456_789) == "-₹12,34,567.89"


@pytest.mark.parametrize(
    "transaction_date",
    ["", "2026-02-30", "03/05/2026", datetime(2026, 1, 1, 12, 30)],
)
def test_invalid_dates_are_rejected(db_connection, transaction_date):
    food_id = category_id(db_connection, "Food", "expense")

    with pytest.raises(TransactionValidationError, match="date"):
        create_transaction(
            db_connection,
            transaction_date,
            "10",
            "expense",
            food_id,
            "Cash",
        )


@pytest.mark.parametrize(
    ("transaction_type", "category_name", "category_type"),
    [
        ("expense", "Salary", "income"),
        ("income", "Food", "expense"),
    ],
)
def test_category_type_must_match_transaction_type(
    db_connection,
    transaction_type,
    category_name,
    category_type,
):
    mismatched_id = category_id(db_connection, category_name, category_type)

    with pytest.raises(TransactionValidationError, match="matching"):
        create_transaction(
            db_connection,
            "2026-01-01",
            "100",
            transaction_type,
            mismatched_id,
            "Cash",
        )


@pytest.mark.parametrize(
    ("transaction_type", "category_id_value", "payment_method"),
    [
        ("transfer", 1, "Cash"),
        ("expense", 0, "Cash"),
        ("expense", 1, ""),
    ],
)
def test_required_and_enum_fields_are_validated(
    db_connection,
    transaction_type,
    category_id_value,
    payment_method,
):
    with pytest.raises(TransactionValidationError):
        create_transaction(
            db_connection,
            "2026-01-01",
            "100",
            transaction_type,
            category_id_value,
            payment_method,
        )


def test_history_filters_date_type_category_and_description(db_connection):
    salary_id = category_id(db_connection, "Salary", "income")
    food_id = category_id(db_connection, "Food", "expense")
    transportation_id = category_id(db_connection, "Transportation", "expense")
    create_transaction(db_connection, "2026-01-03", "3000", "income", salary_id, "Bank", "Pay")
    groceries = create_transaction(
        db_connection,
        "2026-01-05",
        "80",
        "expense",
        food_id,
        "UPI",
        "Weekly groceries",
    )
    create_transaction(
        db_connection,
        "2026-01-10",
        "40",
        "expense",
        transportation_id,
        "Card",
        "Bus ticket",
    )
    create_transaction(
        db_connection,
        "2026-02-05",
        "90",
        "expense",
        food_id,
        "UPI",
        "Monthly groceries",
    )

    filtered = list_transaction_history(
        db_connection,
        date(2026, 1, 1),
        date(2026, 1, 31),
        "expense",
        food_id,
        "GROCER",
    )

    assert len(filtered) == 1
    assert filtered[0].transaction.id == groceries.id
    assert filtered[0].category_name == "Food"


def test_history_rejects_reversed_date_range(db_connection):
    with pytest.raises(TransactionValidationError, match="Start date"):
        list_transaction_history(
            db_connection,
            "2026-02-01",
            "2026-01-01",
        )
