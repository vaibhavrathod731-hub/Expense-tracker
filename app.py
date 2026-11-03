"""Streamlit entry point for the SmartSpend application."""

from dataclasses import asdict

import pandas as pd
import streamlit as st

from smartspend.config import load_settings
from smartspend.db.errors import SmartSpendDatabaseError
from smartspend.db.schema import initialize_database
from smartspend.demo_data import DEMO_TRANSACTIONS
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
selected_page = st.sidebar.radio("Navigation", ("Dashboard", "Transactions"))

if selected_page == "Transactions":
    render_transactions_page(database_path)
else:
    st.title("SmartSpend")
    st.caption("Smart Expense Tracker & Financial Analytics System")
    st.info(
        "The local SQLite database is initialized. Dashboard calculations and analytics "
        "will be added in upcoming phases."
    )

    st.subheader("Sample transaction data")
    st.dataframe(
        pd.DataFrame(asdict(transaction) for transaction in DEMO_TRANSACTIONS),
        hide_index=True,
    )
    st.caption("All displayed transactions are synthetic and are not saved to a database.")
