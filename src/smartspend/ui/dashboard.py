"""Interactive Streamlit financial dashboard."""

import calendar
from datetime import date
from math import isnan

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from smartspend.db.connection import open_connection
from smartspend.db.errors import SmartSpendDatabaseError
from smartspend.repositories.transactions import list_transactions
from smartspend.services.analytics import (
    AnalyticsValidationError,
    DashboardAnalytics,
    get_dashboard_analytics,
)
from smartspend.services.budgets import BudgetValidationError, get_budget_overview
from smartspend.services.transactions import format_paise_as_rupees

CHART_LAYOUT = {
    "template": "plotly_white",
    "font": {"family": "Arial, sans-serif", "color": "#253247"},
    "margin": {"l": 12, "r": 12, "t": 52, "b": 12},
    "legend": {"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
    "hoverlabel": {"font": {"family": "Arial, sans-serif"}},
}


def _date_filters(connection) -> tuple[date, date]:
    transactions = list_transactions(connection)
    transaction_dates = [
        date.fromisoformat(transaction.transaction_date) for transaction in transactions
    ]
    latest = max(transaction_dates) if transaction_dates else date.today()
    available_years = sorted({item.year for item in transaction_dates}, reverse=True)
    if not available_years:
        available_years = [date.today().year]

    filter_type = st.radio(
        "Date filter",
        ("Month", "Year", "Custom range"),
        horizontal=True,
        key="dashboard_filter_type",
    )
    if filter_type == "Month":
        year = st.selectbox(
            "Year",
            available_years,
            index=available_years.index(latest.year) if latest.year in available_years else 0,
            key="dashboard_month_year",
        )
        month_options = list(range(1, 13))
        month = st.selectbox(
            "Month",
            month_options,
            index=latest.month - 1 if year == latest.year else 0,
            format_func=lambda value: date(year, value, 1).strftime("%B"),
            key="dashboard_month",
        )
        return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])

    if filter_type == "Year":
        year = st.selectbox(
            "Year",
            available_years,
            index=available_years.index(latest.year) if latest.year in available_years else 0,
            key="dashboard_year",
        )
        return date(year, 1, 1), date(year, 12, 31)

    range_start = min(transaction_dates) if transaction_dates else date.today()
    range_end = max(transaction_dates) if transaction_dates else date.today()
    selected_range = st.date_input(
        "Date range",
        value=(range_start, range_end),
        key="dashboard_custom_range",
    )
    if not isinstance(selected_range, tuple) or len(selected_range) != 2:
        return range_start, range_end
    return selected_range[0], selected_range[1]


def _rupees(amount_paise: int) -> str:
    return format_paise_as_rupees(int(amount_paise))


def _metric_row(analytics: DashboardAnalytics) -> None:
    summary = analytics.summary
    metrics = st.columns(5)
    metrics[0].metric("Total Income", _rupees(summary.total_income_paise))
    metrics[1].metric("Total Expenses", _rupees(summary.total_expenses_paise))
    metrics[2].metric("Net Savings", _rupees(summary.net_savings_paise))
    metrics[3].metric("Current Balance · All time", _rupees(summary.current_balance_paise))
    metrics[4].metric("Savings Rate", f"{summary.savings_rate_percent:.1f}%")
    st.caption(
        "Income, expenses, savings, and savings rate reflect the selected period. "
        "Current balance is all-time income minus all-time expenses."
    )


def _monthly_income_expense_chart(monthly) -> go.Figure:
    figure = go.Figure()
    for column, title, color in (
        ("income_paise", "Income", "#16a085"),
        ("expenses_paise", "Expenses", "#e76f51"),
    ):
        figure.add_bar(
            x=monthly["month"],
            y=monthly[column] / 100,
            name=title,
            marker_color=color,
            customdata=[_rupees(value) for value in monthly[column]],
            hovertemplate="%{x}<br>" + title + ": %{customdata}<extra></extra>",
        )
    figure.update_layout(
        **CHART_LAYOUT,
        title="Monthly income vs expenses",
        barmode="group",
        xaxis_title=None,
        yaxis_title="Amount (₹)",
        yaxis_tickprefix="₹",
        yaxis_tickformat=",.0f",
    )
    return figure


def _category_chart(categories) -> go.Figure:
    chart_data = categories.assign(
        amount_rupees=categories["amount_paise"] / 100,
        amount_display=categories["amount_paise"].map(_rupees),
    )
    figure = px.pie(
        chart_data,
        names="category",
        values="amount_rupees",
        hole=0.58,
        color_discrete_sequence=px.colors.qualitative.Set2,
        custom_data=["amount_display", "percentage"],
    )
    figure.update_traces(
        textposition="inside",
        textinfo="percent",
        hovertemplate=(
            "%{label}<br>Spending: %{customdata[0]}<br>Share: %{customdata[1]:.1f}%<extra></extra>"
        ),
    )
    figure.update_layout(**CHART_LAYOUT, title="Expense breakdown by category")
    return figure


def _line_chart(monthly, value_column: str, title: str, color: str) -> go.Figure:
    figure = go.Figure(
        go.Scatter(
            x=monthly["month"],
            y=monthly[value_column] / 100,
            mode="lines+markers",
            line={"color": color, "width": 3},
            marker={"size": 7},
            customdata=[_rupees(value) for value in monthly[value_column]],
            hovertemplate="%{x}<br>" + title + ": %{customdata}<extra></extra>",
        )
    )
    figure.update_layout(
        **CHART_LAYOUT,
        title=title,
        xaxis_title=None,
        yaxis_title="Amount (₹)",
        yaxis_tickprefix="₹",
        yaxis_tickformat=",.0f",
    )
    return figure


def _monthly_detail(monthly) -> None:
    detail = monthly[
        [
            "month",
            "income_paise",
            "expenses_paise",
            "savings_paise",
            "expense_change_paise",
            "expense_change_percent",
        ]
    ].copy()
    detail.columns = [
        "Month",
        "Income",
        "Expenses",
        "Savings",
        "Expense change",
        "Expense change (%)",
    ]
    for column in ("Income", "Expenses", "Savings", "Expense change"):
        detail[column] = detail[column].map(_rupees)
    detail["Month"] = detail["Month"].map(
        lambda value: date.fromisoformat(f"{value}-01").strftime("%b %Y")
    )
    detail["Expense change (%)"] = detail["Expense change (%)"].map(
        lambda value: "N/A" if isnan(value) else f"{value:+.1f}%"
    )
    st.dataframe(detail, hide_index=True)


def _category_detail(categories) -> None:
    if categories.empty:
        st.info("No expenses found for this period.")
        return

    table = categories.head(5).copy()
    table["Spending"] = table["amount_paise"].map(_rupees)
    table["Share"] = table["percentage"].map(lambda value: f"{value:.1f}%")
    table = table.rename(columns={"category": "Category"})[["Category", "Spending", "Share"]]
    highest = categories.iloc[0]
    st.metric(
        "Highest spending category",
        str(highest["category"]),
        _rupees(int(highest["amount_paise"])),
    )
    st.dataframe(table, hide_index=True)


def _budget_summary(overview) -> None:
    st.subheader("Budget overview")
    st.caption("Budget totals include full calendar months overlapping the selected date range.")
    metrics = st.columns(3)
    metrics[0].metric("Total budget", _rupees(overview.total_budget_paise))
    metrics[1].metric("Budgeted-category spend", _rupees(overview.total_spent_paise))
    metrics[2].metric("Budget remaining", _rupees(overview.remaining_paise))
    if not overview.items:
        st.info("No category budgets are configured for this date range.")
        return

    alerts = [item for item in overview.items if item.alert_level is not None]
    if not alerts:
        st.success("All budgeted categories are below the 75% alert threshold.")
    for item in alerts:
        message = (
            f"{item.month[:7]} · {item.category_name}: {item.alert_message} "
            f"({_rupees(item.spent_paise)} of {_rupees(item.limit_paise)})."
        )
        if item.alert_level == 100 and item.percent_used > 100:
            st.error(message)
        else:
            st.warning(message)


def render_dashboard_page(database_path) -> None:
    """Render period filters, financial summaries, and interactive analytics."""
    st.title("Financial Dashboard")
    st.caption("Insights from transactions saved in your local SQLite database.")
    try:
        with open_connection(database_path) as connection:
            start_date, end_date = _date_filters(connection)
            if start_date > end_date:
                st.error("Start date must not be after end date.")
                return
            analytics = get_dashboard_analytics(connection, start_date, end_date)
            budgets = get_budget_overview(connection, start_date, end_date)
    except (SmartSpendDatabaseError, AnalyticsValidationError, BudgetValidationError) as error:
        st.error(f"Could not load financial analytics: {error}")
        return

    _metric_row(analytics)
    _budget_summary(budgets)
    st.divider()
    if analytics.transaction_count == 0:
        st.info("No transactions were found for this period. Add transactions to see analytics.")

    first_row = st.columns(2)
    first_row[0].plotly_chart(
        _monthly_income_expense_chart(analytics.monthly),
        width="stretch",
    )
    if analytics.categories.empty:
        first_row[1].info("No expense category data is available for this period.")
    else:
        first_row[1].plotly_chart(
            _category_chart(analytics.categories),
            width="stretch",
        )

    second_row = st.columns(2)
    second_row[0].plotly_chart(
        _line_chart(
            analytics.monthly,
            "expenses_paise",
            "Monthly spending",
            "#e76f51",
        ),
        width="stretch",
    )
    second_row[1].plotly_chart(
        _line_chart(
            analytics.monthly,
            "savings_paise",
            "Monthly savings trend",
            "#16a085",
        ),
        width="stretch",
    )

    with st.expander("Monthly comparison and savings", expanded=False):
        _monthly_detail(analytics.monthly)
    with st.expander("Top 5 expense categories", expanded=True):
        _category_detail(analytics.categories)
