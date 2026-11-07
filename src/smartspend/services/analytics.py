"""Financial dashboard calculations based on persisted transactions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from smartspend.db.models import Category, Transaction
from smartspend.repositories.categories import list_categories
from smartspend.repositories.transactions import list_transactions


class AnalyticsValidationError(ValueError):
    """Raised when an analytics date range is invalid."""


@dataclass(frozen=True, slots=True)
class FinancialSummary:
    """Financial totals in integer paise for the selected period."""

    total_income_paise: int
    total_expenses_paise: int
    net_savings_paise: int
    savings_rate_percent: float
    current_balance_paise: int


@dataclass(frozen=True, slots=True)
class DashboardAnalytics:
    """Summary metrics and aggregates used by the dashboard."""

    summary: FinancialSummary
    monthly: pd.DataFrame
    categories: pd.DataFrame
    transaction_count: int


def _parse_date(value: date | str, label: str) -> date:
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise AnalyticsValidationError(f"{label} must be a valid date.")
    try:
        parsed = date.fromisoformat(value.strip())
    except ValueError:
        raise AnalyticsValidationError(f"{label} must be a valid YYYY-MM-DD date.") from None
    if parsed.isoformat() != value.strip():
        raise AnalyticsValidationError(f"{label} must be a valid YYYY-MM-DD date.")
    return parsed


def _transaction_frame(
    transactions: list[Transaction],
    categories: list[Category],
) -> pd.DataFrame:
    category_names = {category.id: category.name for category in categories}
    return pd.DataFrame(
        [
            {
                "transaction_date": pd.Timestamp(transaction.transaction_date),
                "amount_paise": transaction.amount_paise,
                "transaction_type": transaction.transaction_type,
                "category_id": transaction.category_id,
                "category_name": category_names.get(transaction.category_id, "Unknown"),
            }
            for transaction in transactions
        ],
        columns=[
            "transaction_date",
            "amount_paise",
            "transaction_type",
            "category_id",
            "category_name",
        ],
    )


def _monthly_aggregates(frame: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    months = pd.date_range(
        start=pd.Timestamp(start).to_period("M").start_time,
        end=pd.Timestamp(end).to_period("M").start_time,
        freq="MS",
    )
    monthly = pd.DataFrame({"month": months.strftime("%Y-%m")})
    if frame.empty:
        monthly["income_paise"] = 0
        monthly["expenses_paise"] = 0
    else:
        data = frame.assign(month=frame["transaction_date"].dt.strftime("%Y-%m"))
        grouped = data.pivot_table(
            index="month",
            columns="transaction_type",
            values="amount_paise",
            aggfunc="sum",
            fill_value=0,
        )
        for column in ("income", "expense"):
            if column not in grouped:
                grouped[column] = 0
        grouped = grouped.rename(columns={"income": "income_paise", "expense": "expenses_paise"})
        monthly = monthly.merge(
            grouped[["income_paise", "expenses_paise"]],
            how="left",
            left_on="month",
            right_index=True,
        ).fillna(0)
        monthly[["income_paise", "expenses_paise"]] = monthly[
            ["income_paise", "expenses_paise"]
        ].astype("int64")

    monthly["savings_paise"] = monthly["income_paise"] - monthly["expenses_paise"]
    monthly["expense_change_paise"] = monthly["expenses_paise"].diff().fillna(0).astype("int64")
    previous_expenses = monthly["expenses_paise"].shift(1)
    monthly["expense_change_percent"] = np.select(
        [
            previous_expenses.isna(),
            previous_expenses.eq(0) & monthly["expenses_paise"].eq(0),
            previous_expenses.gt(0),
        ],
        [
            0.0,
            0.0,
            monthly["expense_change_paise"] / previous_expenses.where(previous_expenses != 0) * 100,
        ],
        default=np.nan,
    )
    return monthly


def _category_aggregates(frame: pd.DataFrame) -> pd.DataFrame:
    expense_frame = frame.loc[frame["transaction_type"] == "expense"]
    columns = ["category_id", "category", "amount_paise", "percentage"]
    if expense_frame.empty:
        return pd.DataFrame(columns=columns)

    grouped = (
        expense_frame.groupby(["category_id", "category_name"], as_index=False)["amount_paise"]
        .sum()
        .sort_values(["amount_paise", "category_name"], ascending=[False, True])
        .reset_index(drop=True)
    )
    grouped = grouped.rename(columns={"category_name": "category"})
    total_expenses = int(grouped["amount_paise"].sum())
    grouped["percentage"] = grouped["amount_paise"] / total_expenses * 100
    return grouped[columns]


def get_dashboard_analytics(
    connection,
    start_date: date | str,
    end_date: date | str,
) -> DashboardAnalytics:
    """Calculate filtered dashboard summaries and monthly/category analytics."""
    start = _parse_date(start_date, "Start date")
    end = _parse_date(end_date, "End date")
    if start > end:
        raise AnalyticsValidationError("Start date must not be after end date.")

    all_transactions = list_transactions(connection)
    categories = list_categories(connection)
    all_frame = _transaction_frame(all_transactions, categories)

    if all_frame.empty:
        filtered = all_frame.copy()
        current_balance = 0
    else:
        all_frame["transaction_date"] = pd.to_datetime(all_frame["transaction_date"])
        current_balance = int(
            all_frame.loc[all_frame["transaction_type"] == "income", "amount_paise"].sum()
            - all_frame.loc[all_frame["transaction_type"] == "expense", "amount_paise"].sum()
        )
        filtered = all_frame.loc[
            all_frame["transaction_date"].between(
                pd.Timestamp(start),
                pd.Timestamp(end),
                inclusive="both",
            )
        ].copy()

    income = int(filtered.loc[filtered["transaction_type"] == "income", "amount_paise"].sum())
    expenses = int(filtered.loc[filtered["transaction_type"] == "expense", "amount_paise"].sum())
    savings = income - expenses
    savings_rate = savings / income * 100 if income else 0.0
    summary = FinancialSummary(
        total_income_paise=income,
        total_expenses_paise=expenses,
        net_savings_paise=savings,
        savings_rate_percent=savings_rate,
        current_balance_paise=current_balance,
    )
    filtered["transaction_date"] = pd.to_datetime(filtered["transaction_date"])
    return DashboardAnalytics(
        summary=summary,
        monthly=_monthly_aggregates(filtered, start, end),
        categories=_category_aggregates(filtered),
        transaction_count=len(filtered),
    )
