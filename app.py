"""Streamlit entry point for the SmartSpend application."""

from dataclasses import asdict

import pandas as pd
import streamlit as st

from smartspend.config import load_settings
from smartspend.demo_data import DEMO_TRANSACTIONS

st.set_page_config(page_title="SmartSpend", page_icon="💸", layout="wide")

settings = load_settings()

st.sidebar.title("SmartSpend")
st.sidebar.caption("Personal finance, made clearer.")
st.sidebar.caption(f"Local data directory: {settings.data_dir}")

st.title("SmartSpend")
st.caption("Smart Expense Tracker & Financial Analytics System")
st.info(
    "Project foundation is ready. This preview contains synthetic demo data only; "
    "transaction storage and financial summaries will be added in upcoming phases."
)

st.subheader("Sample transaction data")
st.dataframe(
    pd.DataFrame(asdict(transaction) for transaction in DEMO_TRANSACTIONS),
    hide_index=True,
)
st.caption("All displayed transactions are synthetic and are not saved to a database.")
