from datetime import date

import pytest

from smartspend.repositories.categories import list_categories
from smartspend.services.analytics import (
    AnalyticsValidationError,
    get_dashboard_analytics,
)
from smartspend.services.transactions import create_transaction


def category_id(connection, name, category_type):
    return next(
        category.id
        for category in list_categories(connection, category_type)
        if category.name == name
    )


def add_transaction(
    connection,
    transaction_date,
    amount_rupees,
    transaction_type,
    category_name,
    category_type,
    description=None,
):
    return create_transaction(
        connection,
        transaction_date,
        amount_rupees,
        transaction_type,
        category_id(connection, category_name, category_type),
        "UPI",
        description,
    )


def test_income_expenses_savings_rate_and_all_time_balance(db_connection):
    add_transaction(db_connection, "2026-01-05", "50000", "income", "Salary", "income")
    add_transaction(db_connection, "2026-01-10", "12000", "expense", "Rent", "expense")
    add_transaction(db_connection, "2026-02-05", "10000", "income", "Freelancing", "income")
    add_transaction(db_connection, "2026-02-10", "3000", "expense", "Food", "expense")

    january = get_dashboard_analytics(db_connection, "2026-01-01", "2026-01-31")

    assert january.summary.total_income_paise == 5_000_000
    assert january.summary.total_expenses_paise == 1_200_000
    assert january.summary.net_savings_paise == 3_800_000
    assert january.summary.savings_rate_percent == pytest.approx(76.0)
    assert january.summary.current_balance_paise == 4_500_000
    assert january.transaction_count == 2


def test_expense_only_period_has_zero_savings_rate(db_connection):
    add_transaction(db_connection, "2026-01-10", "120", "expense", "Food", "expense")

    analytics = get_dashboard_analytics(db_connection, "2026-01-01", "2026-01-31")

    assert analytics.summary.total_income_paise == 0
    assert analytics.summary.total_expenses_paise == 12_000
    assert analytics.summary.net_savings_paise == -12_000
    assert analytics.summary.savings_rate_percent == 0
    assert analytics.summary.current_balance_paise == -12_000


def test_monthly_aggregation_fills_months_and_compares_expenses(db_connection):
    add_transaction(db_connection, "2026-01-05", "500", "income", "Salary", "income")
    add_transaction(db_connection, "2026-01-10", "100", "expense", "Food", "expense")
    add_transaction(db_connection, "2026-03-05", "800", "income", "Salary", "income")
    add_transaction(db_connection, "2026-03-10", "150", "expense", "Food", "expense")

    analytics = get_dashboard_analytics(db_connection, "2026-01-01", "2026-03-31")
    monthly = analytics.monthly

    assert list(monthly["month"]) == ["2026-01", "2026-02", "2026-03"]
    assert list(monthly["income_paise"]) == [50_000, 0, 80_000]
    assert list(monthly["expenses_paise"]) == [10_000, 0, 15_000]
    assert list(monthly["savings_paise"]) == [40_000, 0, 65_000]
    assert list(monthly["expense_change_paise"]) == [0, -10_000, 15_000]
    assert monthly.iloc[1]["expense_change_percent"] == pytest.approx(-100.0)
    assert monthly.iloc[2]["expense_change_percent"] != monthly.iloc[2]["expense_change_percent"]


def test_category_aggregation_percentages_top_categories_and_highest(db_connection):
    amounts = [
        ("Food", "100"),
        ("Rent", "300"),
        ("Transportation", "200"),
        ("Shopping", "150"),
        ("Healthcare", "50"),
        ("Utilities", "40"),
        ("Education", "30"),
    ]
    for category, amount in amounts:
        add_transaction(
            db_connection,
            "2026-01-10",
            amount,
            "expense",
            category,
            "expense",
        )

    analytics = get_dashboard_analytics(db_connection, "2026-01-01", "2026-01-31")
    categories = analytics.categories

    assert categories.iloc[0]["category"] == "Rent"
    assert categories.iloc[0]["amount_paise"] == 30_000
    assert categories.iloc[0]["percentage"] == pytest.approx(300 / 870 * 100)
    assert list(categories.head(5)["category"]) == [
        "Rent",
        "Transportation",
        "Shopping",
        "Food",
        "Healthcare",
    ]
    assert categories["percentage"].sum() == pytest.approx(100)


def test_empty_database_returns_zero_metrics_and_empty_category_data(db_connection):
    analytics = get_dashboard_analytics(db_connection, date(2026, 1, 1), date(2026, 3, 31))

    assert analytics.summary.total_income_paise == 0
    assert analytics.summary.total_expenses_paise == 0
    assert analytics.summary.net_savings_paise == 0
    assert analytics.summary.savings_rate_percent == 0
    assert analytics.summary.current_balance_paise == 0
    assert analytics.transaction_count == 0
    assert analytics.categories.empty
    assert list(analytics.monthly["month"]) == ["2026-01", "2026-02", "2026-03"]
    assert not analytics.monthly[["income_paise", "expenses_paise"]].to_numpy().any()


def test_date_filters_include_only_transactions_in_selected_period(db_connection):
    add_transaction(db_connection, "2025-12-31", "100", "income", "Salary", "income")
    add_transaction(db_connection, "2026-01-01", "200", "income", "Salary", "income")
    add_transaction(db_connection, "2026-02-01", "50", "expense", "Food", "expense")

    analytics = get_dashboard_analytics(db_connection, "2026-01-01", "2026-01-31")

    assert analytics.summary.total_income_paise == 20_000
    assert analytics.summary.total_expenses_paise == 0
    assert analytics.transaction_count == 1
    assert analytics.summary.current_balance_paise == 25_000


@pytest.mark.parametrize(
    ("start_date", "end_date"),
    [
        ("2026-02-30", "2026-03-01"),
        ("2026-03-01", "2026-02-01"),
        ("03/01/2026", "2026-03-31"),
    ],
)
def test_invalid_date_ranges_are_rejected(db_connection, start_date, end_date):
    with pytest.raises(AnalyticsValidationError):
        get_dashboard_analytics(db_connection, start_date, end_date)
