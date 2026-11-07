"""Streamlit monthly category budget management page."""

import calendar
from datetime import date

import pandas as pd
import streamlit as st

from smartspend.db.connection import open_connection
from smartspend.db.errors import SmartSpendDatabaseError
from smartspend.repositories.budgets import list_budgets
from smartspend.services.budgets import (
    BudgetValidationError,
    create_category_budget,
    delete_category_budget,
    expense_categories,
    get_budget_overview,
    update_category_budget,
)
from smartspend.services.transactions import format_paise_as_rupees


def _show_success_and_refresh(message: str) -> None:
    st.session_state["budget_notice"] = message
    st.rerun()


def _money(amount_paise: int) -> str:
    return format_paise_as_rupees(amount_paise)


def _budget_month_selector(key: str) -> date:
    today = date.today()
    month = st.selectbox(
        "Budget month",
        range(1, 13),
        index=today.month - 1,
        format_func=lambda value: date(today.year, value, 1).strftime("%B"),
        key=f"{key}_month",
    )
    year = st.number_input(
        "Budget year",
        min_value=2000,
        max_value=9999,
        value=today.year,
        step=1,
        key=f"{key}_year",
    )
    return date(int(year), month, 1)


def _budget_summary(overview) -> None:
    metrics = st.columns(3)
    metrics[0].metric("Total budget", _money(overview.total_budget_paise))
    metrics[1].metric("Budgeted-category spend", _money(overview.total_spent_paise))
    metrics[2].metric("Remaining budget", _money(overview.remaining_paise))
    if not overview.items:
        st.info("No category budgets are set for this month.")
        return

    rows = []
    for item in overview.items:
        rows.append(
            {
                "Category": item.category_name,
                "Budget": _money(item.limit_paise),
                "Spent": _money(item.spent_paise),
                "Remaining": _money(item.remaining_paise),
                "Used": f"{item.percent_used:.1f}%",
                "Status": item.alert_message or "On track",
            }
        )
        progress = min(item.percent_used / 100, 1.0)
        st.progress(progress, text=f"{item.category_name}: {item.percent_used:.1f}% used")
        if item.alert_level == 100:
            if item.percent_used > 100:
                st.error(
                    f"{item.category_name}: {item.alert_message} "
                    f"({_money(item.spent_paise)} of {_money(item.limit_paise)})."
                )
            else:
                st.warning(
                    f"{item.category_name}: {item.alert_message} "
                    f"({_money(item.spent_paise)} of {_money(item.limit_paise)})."
                )
        elif item.alert_level in (75, 90):
            st.warning(
                f"{item.category_name}: {item.alert_message} "
                f"({_money(item.spent_paise)} of {_money(item.limit_paise)})."
            )
    st.dataframe(pd.DataFrame(rows), hide_index=True)


def _add_budget_form(connection, month: date) -> None:
    st.subheader("Set a category budget")
    categories = expense_categories(connection)
    if not categories:
        st.info("Add an expense category before creating a budget.")
        return

    with st.form("create_category_budget"):
        category = st.selectbox("Expense category", categories, format_func=lambda item: item.name)
        amount = st.text_input("Monthly limit (₹)", placeholder="e.g. 15000.00")
        submitted = st.form_submit_button("Save budget", type="primary")
    if submitted:
        try:
            created = create_category_budget(connection, month, amount, category.id)
        except (BudgetValidationError, SmartSpendDatabaseError) as error:
            st.error(f"Could not save budget: {error}")
        else:
            _show_success_and_refresh(
                f"{category.name} budget saved at {_money(created.amount_paise)}."
            )


def _edit_budget_form(connection, month: date) -> None:
    budgets = [
        budget
        for budget in list_budgets(connection, month.isoformat())
        if budget.category_id is not None
    ]
    if not budgets:
        st.info("There are no category budgets to edit this month.")
        return

    categories = {category.id: category for category in expense_categories(connection)}
    selected = st.selectbox(
        "Budget to edit",
        budgets,
        format_func=lambda budget: (
            f"{categories[budget.category_id].name} — {_money(budget.amount_paise)}"
        ),
    )
    with st.form("edit_category_budget"):
        category_options = expense_categories(connection)
        selected_category = st.selectbox(
            "Expense category",
            category_options,
            index=next(
                (
                    index
                    for index, category in enumerate(category_options)
                    if category.id == selected.category_id
                ),
                0,
            ),
            format_func=lambda item: item.name,
        )
        amount = st.text_input(
            "Monthly limit (₹)",
            value=f"{selected.amount_paise // 100}.{selected.amount_paise % 100:02d}",
        )
        submitted = st.form_submit_button("Update budget", type="primary")
    if submitted:
        try:
            updated = update_category_budget(
                connection,
                selected.id,
                month,
                amount,
                selected_category.id,
            )
        except (BudgetValidationError, SmartSpendDatabaseError) as error:
            st.error(f"Could not update budget: {error}")
        else:
            _show_success_and_refresh(
                f"{selected_category.name} budget updated to {_money(updated.amount_paise)}."
            )


def _delete_budget_form(connection, month: date) -> None:
    budgets = [
        budget
        for budget in list_budgets(connection, month.isoformat())
        if budget.category_id is not None
    ]
    if not budgets:
        st.info("There are no category budgets to delete this month.")
        return

    categories = {category.id: category for category in expense_categories(connection)}
    selected = st.selectbox(
        "Budget to delete",
        budgets,
        format_func=lambda budget: (
            f"{categories[budget.category_id].name} — {_money(budget.amount_paise)}"
        ),
        key="delete_budget_selection",
    )
    with st.form("delete_category_budget"):
        confirmed = st.checkbox(
            f"Confirm deletion of the {categories[selected.category_id].name} budget"
        )
        submitted = st.form_submit_button("Delete budget")
    if submitted:
        if not confirmed:
            st.warning("Confirm the deletion before continuing.")
            return
        try:
            delete_category_budget(connection, selected.id)
        except (BudgetValidationError, SmartSpendDatabaseError) as error:
            st.error(f"Could not delete budget: {error}")
        else:
            _show_success_and_refresh("Budget deleted.")


def render_budgets_page(database_path) -> None:
    """Render budget utilization, alerts, and monthly category budget CRUD."""
    st.title("Monthly Budgets")
    st.caption("Set category limits and keep an eye on spending throughout the month.")
    notice = st.session_state.pop("budget_notice", None)
    if notice:
        st.success(notice)
    try:
        with open_connection(database_path) as connection:
            month = _budget_month_selector("budgets")
            month_end = month.replace(day=calendar.monthrange(month.year, month.month)[1])
            overview = get_budget_overview(connection, month, month_end)
            _budget_summary(overview)
            st.divider()
            add_tab, edit_tab, delete_tab = st.tabs(("Add", "Edit", "Delete"))
            with add_tab:
                _add_budget_form(connection, month)
            with edit_tab:
                _edit_budget_form(connection, month)
            with delete_tab:
                _delete_budget_form(connection, month)
    except SmartSpendDatabaseError as error:
        st.error(f"Could not load budgets: {error}")
