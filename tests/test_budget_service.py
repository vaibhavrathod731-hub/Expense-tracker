from datetime import date
from decimal import Decimal

import pytest

from smartspend.db.errors import DatabaseIntegrityError
from smartspend.repositories.budgets import list_budgets
from smartspend.repositories.categories import list_categories
from smartspend.services.budgets import (
    BudgetValidationError,
    create_category_budget,
    delete_category_budget,
    get_budget_overview,
    update_category_budget,
)
from smartspend.services.transactions import create_transaction


def category_id(connection, name, category_type="expense"):
    return next(
        category.id
        for category in list_categories(connection, category_type)
        if category.name == name
    )


def add_expense(connection, transaction_date, amount, category="Food"):
    return create_transaction(
        connection,
        transaction_date,
        str(amount),
        "expense",
        category_id(connection, category),
        "UPI",
        "Test expense",
    )


@pytest.mark.parametrize(
    ("spent", "expected_level", "expected_message"),
    [
        ("74.99", None, None),
        ("75", 75, "75% or more of budget used"),
        ("90", 90, "90% or more of budget used"),
        ("100", 100, "100% of budget used"),
        ("125", 100, "Over budget"),
    ],
)
def test_budget_thresholds_and_over_budget_amounts(
    db_connection,
    spent,
    expected_level,
    expected_message,
):
    food_id = category_id(db_connection, "Food")
    create_category_budget(db_connection, "2026-03", "100", food_id)
    add_expense(db_connection, "2026-03-15", spent)

    overview = get_budget_overview(db_connection, "2026-03-01", "2026-03-31")

    assert overview.total_budget_paise == 10_000
    spent_paise = int(Decimal(spent) * 100)
    assert overview.total_spent_paise == spent_paise
    assert overview.remaining_paise == 10_000 - spent_paise
    assert overview.items[0].percent_used == pytest.approx(float(spent))
    assert overview.items[0].alert_level == expected_level
    assert overview.items[0].alert_message == expected_message


def test_budget_management_crud_and_amount_conversion(db_connection):
    food_id = category_id(db_connection, "Food")
    rent_id = category_id(db_connection, "Rent")

    created = create_category_budget(db_connection, date(2026, 4, 17), "1250.50", food_id)
    assert created.month == "2026-04-01"
    assert created.amount_paise == 125_050

    updated = update_category_budget(db_connection, created.id, "2026-05", "1500", rent_id)
    assert updated.month == "2026-05-01"
    assert updated.category_id == rent_id
    assert updated.amount_paise == 150_000

    delete_category_budget(db_connection, updated.id)
    assert list_budgets(db_connection, "2026-05-01") == []

    with pytest.raises(BudgetValidationError, match="does not exist"):
        update_category_budget(db_connection, updated.id, "2026-05", "100", rent_id)
    with pytest.raises(BudgetValidationError, match="does not exist"):
        delete_category_budget(db_connection, updated.id)


@pytest.mark.parametrize("amount", ["", "0", "-1", "1.001", "NaN", "Infinity"])
def test_invalid_budget_amounts_are_rejected(db_connection, amount):
    with pytest.raises(BudgetValidationError):
        create_category_budget(
            db_connection,
            "2026-01",
            amount,
            category_id(db_connection, "Food"),
        )


@pytest.mark.parametrize("month", ["", "2026-13", "not-a-month", "2026-02-30"])
def test_invalid_budget_months_are_rejected(db_connection, month):
    with pytest.raises(BudgetValidationError):
        create_category_budget(
            db_connection,
            month,
            "100",
            category_id(db_connection, "Food"),
        )


def test_income_categories_cannot_have_budgets(db_connection):
    salary_id = category_id(db_connection, "Salary", "income")

    with pytest.raises(BudgetValidationError, match="expense categories"):
        create_category_budget(db_connection, "2026-01", "100", salary_id)


def test_duplicate_category_month_budget_surfaces_database_error(db_connection):
    food_id = category_id(db_connection, "Food")
    create_category_budget(db_connection, "2026-01", "100", food_id)

    with pytest.raises(DatabaseIntegrityError):
        create_category_budget(db_connection, "2026-01", "200", food_id)


def test_budget_overview_handles_no_budgets_and_no_expenses(db_connection):
    empty = get_budget_overview(db_connection, "2026-01-01", "2026-01-31")
    assert empty.total_budget_paise == 0
    assert empty.total_spent_paise == 0
    assert empty.remaining_paise == 0
    assert empty.items == ()

    food_id = category_id(db_connection, "Food")
    create_category_budget(db_connection, "2026-01", "100", food_id)
    overview = get_budget_overview(db_connection, "2026-01-01", "2026-01-31")

    assert overview.total_budget_paise == 10_000
    assert overview.total_spent_paise == 0
    assert overview.remaining_paise == 10_000
    assert overview.items[0].percent_used == 0
    assert overview.items[0].alert_message is None


def test_budget_overview_aggregates_months_without_counting_other_categories(
    db_connection,
):
    food_id = category_id(db_connection, "Food")
    rent_id = category_id(db_connection, "Rent")
    create_category_budget(db_connection, "2026-01", "100", food_id)
    create_category_budget(db_connection, "2026-02", "200", food_id)
    create_category_budget(db_connection, "2026-02", "300", rent_id)
    add_expense(db_connection, "2026-01-15", "75")
    add_expense(db_connection, "2026-02-15", "100")
    add_expense(db_connection, "2026-02-16", "50", "Rent")
    add_expense(db_connection, "2026-02-17", "500", "Shopping")

    overview = get_budget_overview(db_connection, "2026-01-01", "2026-02-28")

    assert overview.total_budget_paise == 60_000
    assert overview.total_spent_paise == 22_500
    assert overview.remaining_paise == 37_500
    assert {item.category_name for item in overview.items} == {"Food", "Rent"}


def test_invalid_budget_date_range_is_rejected(db_connection):
    with pytest.raises(BudgetValidationError, match="must not be after"):
        get_budget_overview(db_connection, "2026-02-01", "2026-01-31")
