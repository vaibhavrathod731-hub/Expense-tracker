"""Monthly expense budgets, utilization calculations, and spending alerts."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime

from smartspend.db.models import Budget
from smartspend.repositories.budgets import (
    create_budget as repository_create_budget,
)
from smartspend.repositories.budgets import (
    delete_budget as repository_delete_budget,
)
from smartspend.repositories.budgets import (
    get_budget as repository_get_budget,
)
from smartspend.repositories.budgets import (
    list_budgets,
)
from smartspend.repositories.budgets import (
    update_budget as repository_update_budget,
)
from smartspend.repositories.categories import get_category, list_categories
from smartspend.repositories.transactions import list_transactions
from smartspend.services.transactions import (
    RupeeAmount,
    TransactionValidationError,
    rupees_to_paise,
)

BUDGET_ALERT_THRESHOLDS = (75, 90, 100)


class BudgetValidationError(ValueError):
    """Raised when budget input or period is invalid."""


@dataclass(frozen=True, slots=True)
class BudgetTrackingItem:
    """A monthly category budget with actual spend and alert state."""

    month: str
    category_id: int
    category_name: str
    limit_paise: int
    spent_paise: int
    remaining_paise: int
    percent_used: float
    alert_level: int | None
    alert_message: str | None


@dataclass(frozen=True, slots=True)
class BudgetOverview:
    """Category budget totals across one or more months."""

    total_budget_paise: int
    total_spent_paise: int
    remaining_paise: int
    items: tuple[BudgetTrackingItem, ...]


def _normalize_month(month: date | str) -> str:
    if isinstance(month, datetime):
        raise BudgetValidationError("Choose a month without a time.")
    if isinstance(month, date):
        return month.replace(day=1).isoformat()
    if not isinstance(month, str):
        raise BudgetValidationError("Choose a valid budget month.")
    value = month.strip()
    if len(value) == 7:
        try:
            return date.fromisoformat(f"{value}-01").isoformat()
        except ValueError:
            raise BudgetValidationError("Enter a valid budget month as YYYY-MM.") from None
    try:
        parsed_month = date.fromisoformat(value)
    except ValueError:
        raise BudgetValidationError(
            "Enter a valid budget month as YYYY-MM or YYYY-MM-DD."
        ) from None
    return parsed_month.replace(day=1).isoformat()


def _month_range(start_date: date | str, end_date: date | str) -> tuple[str, ...]:
    try:
        start = _parse_range_date(start_date, is_end=False)
        end = _parse_range_date(end_date, is_end=True)
    except ValueError:
        raise BudgetValidationError("Choose a valid budget date range.") from None
    if not isinstance(start, date) or not isinstance(end, date) or start > end:
        raise BudgetValidationError("Budget range start must not be after its end.")

    months = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append(date(year, month, 1).isoformat())
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
    return tuple(months)


def _parse_range_date(value: date | str, *, is_end: bool) -> date:
    if isinstance(value, datetime):
        raise ValueError("Date range does not accept a datetime.")
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError("Date range must contain dates.")
    text = value.strip()
    if len(text) == 7:
        month_start = date.fromisoformat(f"{text}-01")
        if is_end:
            return month_start.replace(
                day=calendar.monthrange(month_start.year, month_start.month)[1]
            )
        return month_start
    return date.fromisoformat(text)


def _validate_category(connection, category_id: int) -> str:
    if isinstance(category_id, bool) or not isinstance(category_id, int) or category_id < 1:
        raise BudgetValidationError("Choose a valid expense category.")
    category = get_category(connection, category_id)
    if category is None or category.category_type != "expense":
        raise BudgetValidationError("Budgets can only be assigned to expense categories.")
    return category.name


def create_category_budget(
    connection,
    month: date | str,
    amount: RupeeAmount,
    category_id: int,
) -> Budget:
    """Validate form values and create a monthly expense-category budget."""
    normalized_month = _normalize_month(month)
    _validate_category(connection, category_id)
    try:
        amount_paise = rupees_to_paise(amount)
    except TransactionValidationError as exc:
        raise BudgetValidationError(str(exc)) from exc
    return repository_create_budget(connection, normalized_month, amount_paise, category_id)


def update_category_budget(
    connection,
    budget_id: int,
    month: date | str,
    amount: RupeeAmount,
    category_id: int,
) -> Budget:
    """Validate form values and update a monthly expense-category budget."""
    normalized_month = _normalize_month(month)
    _validate_category(connection, category_id)
    try:
        amount_paise = rupees_to_paise(amount)
    except TransactionValidationError as exc:
        raise BudgetValidationError(str(exc)) from exc
    existing = repository_get_budget(connection, budget_id)
    if existing is None:
        raise BudgetValidationError(f"Budget {budget_id} does not exist.")
    return repository_update_budget(
        connection,
        budget_id,
        normalized_month,
        amount_paise,
        category_id,
    )


def delete_category_budget(connection, budget_id: int) -> None:
    """Delete an existing category budget."""
    if repository_get_budget(connection, budget_id) is None:
        raise BudgetValidationError(f"Budget {budget_id} does not exist.")
    repository_delete_budget(connection, budget_id)


def _alert_state(percent_used: float) -> tuple[int | None, str | None]:
    if percent_used > BUDGET_ALERT_THRESHOLDS[-1]:
        return BUDGET_ALERT_THRESHOLDS[-1], "Over budget"
    if percent_used >= BUDGET_ALERT_THRESHOLDS[-1]:
        return BUDGET_ALERT_THRESHOLDS[-1], "100% of budget used"
    if percent_used >= BUDGET_ALERT_THRESHOLDS[-2]:
        return BUDGET_ALERT_THRESHOLDS[-2], "90% or more of budget used"
    if percent_used >= BUDGET_ALERT_THRESHOLDS[-3]:
        return BUDGET_ALERT_THRESHOLDS[-3], "75% or more of budget used"
    return None, None


def get_budget_overview(
    connection,
    start_date: date | str,
    end_date: date | str,
) -> BudgetOverview:
    """Calculate utilization for category budgets in each month of a date range."""
    months = _month_range(start_date, end_date)
    budgets = [
        budget
        for month in months
        for budget in list_budgets(connection, month)
        if budget.category_id is not None
    ]
    categories = {category.id: category for category in list_categories(connection, "expense")}
    spend_by_month_category: dict[tuple[str, int], int] = {}
    for transaction in list_transactions(connection):
        if transaction.transaction_type != "expense" or transaction.category_id is None:
            continue
        transaction_month = f"{transaction.transaction_date[:7]}-01"
        key = (transaction_month, transaction.category_id)
        spend_by_month_category[key] = (
            spend_by_month_category.get(key, 0) + transaction.amount_paise
        )

    items = []
    for budget in budgets:
        category = categories.get(budget.category_id)
        if category is None:
            continue
        spent = spend_by_month_category.get((budget.month, budget.category_id), 0)
        percent_used = spent / budget.amount_paise * 100
        alert_level, alert_message = _alert_state(percent_used)
        items.append(
            BudgetTrackingItem(
                month=budget.month,
                category_id=category.id,
                category_name=category.name,
                limit_paise=budget.amount_paise,
                spent_paise=spent,
                remaining_paise=budget.amount_paise - spent,
                percent_used=percent_used,
                alert_level=alert_level,
                alert_message=alert_message,
            )
        )

    total_budget = sum(item.limit_paise for item in items)
    total_spent = sum(item.spent_paise for item in items)
    return BudgetOverview(
        total_budget_paise=total_budget,
        total_spent_paise=total_spent,
        remaining_paise=total_budget - total_spent,
        items=tuple(items),
    )


def expense_categories(connection):
    """List categories eligible for monthly budgets."""
    return list_categories(connection, "expense")
