"""Streamlit entry point for the SmartSpend application."""

import streamlit as st

from smartspend.config import load_settings
from smartspend.db.errors import SmartSpendDatabaseError
from smartspend.db.schema import initialize_database
from smartspend.ui.budgets import render_budgets_page
from smartspend.ui.dashboard import render_dashboard_page
from smartspend.ui.transactions import render_transactions_page

st.set_page_config(page_title="SmartSpend", page_icon="💸", layout="wide")

settings = load_settings()
st.sidebar.title("SmartSpend")
st.sidebar.caption("Personal finance, made clearer.")
try:
    database_path = initialize_database(settings.database_path)
except SmartSpendDatabaseError as error:
    st.error(f"Could not initialize the local database: {error}")
    st.stop()

st.sidebar.caption(f"SQLite database: {database_path}")
selected_page = st.sidebar.radio(
    "Navigation",
    ("Dashboard", "Transactions", "Budgets"),
)

if selected_page == "Transactions":
    render_transactions_page(database_path)
elif selected_page == "Budgets":
    render_budgets_page(database_path)
else:
    render_dashboard_page(database_path)
