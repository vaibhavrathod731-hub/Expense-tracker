"""Streamlit entry point for the SmartSpend application."""

from dataclasses import asdict

import pandas as pd
import streamlit as st

from smartspend.config import load_settings
from smartspend.db.schema import initialize_database
from smartspend.demo_data import DEMO_TRANSACTIONS

st.set_page_config(page_title="SmartSpend", page_icon="💸", layout="wide")

settings = load_settings()
database_path = initialize_database(settings.database_path)

st.sidebar.title("SmartSpend")
st.sidebar.caption("Personal finance, made clearer.")
st.sidebar.caption(f"SQLite database: {database_path}")

st.title("SmartSpend")
st.caption("Smart Expense Tracker & Financial Analytics System")
st.info(
    "The local SQLite database is initialized. This preview shows synthetic demo data only; "
    "dashboard calculations and the transaction-management interface are upcoming."
)

st.subheader("Sample transaction data")
st.dataframe(
    pd.DataFrame(asdict(transaction) for transaction in DEMO_TRANSACTIONS),
    hide_index=True,
)
st.caption("All displayed transactions are synthetic and are not saved to a database.")
