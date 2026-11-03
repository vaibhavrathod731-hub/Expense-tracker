"""Streamlit transaction management page."""

from datetime import date

import pandas as pd
import streamlit as st

from smartspend.db.connection import open_connection
from smartspend.db.errors import SmartSpendDatabaseError
from smartspend.services.transactions import (
    TRANSACTION_TYPES,
    TransactionValidationError,
    categories_for_type,
    create_transaction,
    delete_transaction,
    format_paise_as_rupees,
    list_transaction_history,
    update_transaction,
)

PAYMENT_METHODS = ("Cash", "UPI", "Debit card", "Credit card", "Bank transfer", "Other")


def _handle_error(error: Exception) -> None:
    st.error(f"Could not complete the transaction operation: {error}")


def _format_date(value: str) -> str:
    return date.fromisoformat(value).strftime("%d %b %Y")


def _transaction_table(records) -> None:
    if not records:
        st.info("No transactions match the selected filters.")
        return

    rows = [
        {
            "ID": item.transaction.id,
            "Date": _format_date(item.transaction.transaction_date),
            "Type": item.transaction.transaction_type.title(),
            "Category": item.category_name,
            "Description": item.transaction.description or "—",
            "Payment method": item.transaction.payment_method or "—",
            "Amount": format_paise_as_rupees(item.transaction.amount_paise),
        }
        for item in records
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True)


def _add_transaction(connection) -> None:
    st.subheader("Add a transaction")
    transaction_type = st.selectbox(
        "Transaction type",
        TRANSACTION_TYPES,
        format_func=str.title,
        key="add_transaction_type",
    )
    categories = categories_for_type(connection, transaction_type)
    with st.form("add_transaction_form", clear_on_submit=True):
        category = st.selectbox(
            "Category",
            categories,
            format_func=lambda item: item.name,
            key="add_category",
        )
        amount = st.text_input("Amount (₹)", placeholder="e.g. 1250.50")
        transaction_date = st.date_input("Date", value=date.today())
        payment_method = st.selectbox(
            "Payment method",
            ("", *PAYMENT_METHODS),
            format_func=lambda method: method or "Select a payment method",
        )
        description = st.text_input("Description (optional)")
        submitted = st.form_submit_button("Add transaction", type="primary")

    if submitted:
        try:
            created = create_transaction(
                connection,
                transaction_date,
                amount,
                transaction_type,
                category.id,
                payment_method,
                description,
            )
        except (TransactionValidationError, SmartSpendDatabaseError) as error:
            _handle_error(error)
        else:
            st.success(
                f"{created.transaction_type.title()} of "
                f"{format_paise_as_rupees(created.amount_paise)} saved."
            )


def _transaction_filters(connection):
    all_records = list_transaction_history(connection)
    dates = [date.fromisoformat(item.transaction.transaction_date) for item in all_records]
    first_date = min(dates) if dates else date.today()
    last_date = max(dates) if dates else date.today()

    with st.expander("Filter transaction history", expanded=True):
        date_range = st.date_input(
            "Date range",
            value=(first_date, last_date),
            key="history_date_range",
        )
        transaction_type = st.selectbox(
            "Type",
            ("all", *TRANSACTION_TYPES),
            format_func=lambda kind: "All types" if kind == "all" else kind.title(),
            key="history_type",
        )
        categories = categories_for_type(
            connection,
            None if transaction_type == "all" else transaction_type,
        )
        category_names = {category.id: category.name for category in categories}
        category_options = [None, *sorted(category_names)]
        category_id = st.selectbox(
            "Category",
            category_options,
            format_func=lambda identifier: (
                "All categories" if identifier is None else category_names[identifier]
            ),
            key="history_category",
        )
        if transaction_type != "all" and category_id is not None:
            allowed_ids = {category.id for category in categories}
            if category_id not in allowed_ids:
                category_id = None
                st.caption("The selected category does not match this transaction type.")
        description_search = st.text_input(
            "Search description",
            placeholder="Search text",
            key="history_search",
        )

    if not isinstance(date_range, tuple) or len(date_range) != 2:
        return first_date, last_date, transaction_type, category_id, description_search
    return (
        date_range[0],
        date_range[1],
        transaction_type,
        category_id,
        description_search,
    )


def _transaction_history(connection) -> None:
    st.subheader("Transaction history")
    start_date, end_date, transaction_type, category_id, search = _transaction_filters(connection)
    try:
        records = list_transaction_history(
            connection,
            start_date,
            end_date,
            None if transaction_type == "all" else transaction_type,
            category_id,
            search,
        )
    except TransactionValidationError as error:
        st.error(str(error))
        return
    _transaction_table(records)


def _edit_transaction(connection) -> None:
    st.subheader("Edit a transaction")
    records = list_transaction_history(connection)
    if not records:
        st.info("Add a transaction before editing.")
        return

    selected = st.selectbox(
        "Select transaction",
        records,
        format_func=lambda item: (
            f"#{item.transaction.id} · {_format_date(item.transaction.transaction_date)} · "
            f"{item.category_name} · {format_paise_as_rupees(item.transaction.amount_paise)}"
        ),
        key="edit_transaction_selection",
    )
    transaction = selected.transaction
    transaction_type = st.selectbox(
        "Transaction type",
        TRANSACTION_TYPES,
        index=TRANSACTION_TYPES.index(transaction.transaction_type),
        format_func=str.title,
        key=f"edit_type_{transaction.id}",
    )
    categories = categories_for_type(connection, transaction_type)
    category_ids = [category.id for category in categories]
    with st.form(f"edit_transaction_form_{transaction.id}"):
        category = st.selectbox(
            "Category",
            categories,
            index=(
                category_ids.index(transaction.category_id)
                if transaction.category_id in category_ids
                else 0
            ),
            format_func=lambda item: item.name,
            key=f"edit_category_{transaction.id}",
        )
        amount = st.text_input(
            "Amount (₹)",
            value=f"{transaction.amount_paise // 100}.{transaction.amount_paise % 100:02d}",
            key=f"edit_amount_{transaction.id}",
        )
        transaction_date = st.date_input(
            "Date",
            value=date.fromisoformat(transaction.transaction_date),
            key=f"edit_date_{transaction.id}",
        )
        payment_method = st.text_input(
            "Payment method",
            value=transaction.payment_method or "",
            key=f"edit_method_{transaction.id}",
        )
        description = st.text_input(
            "Description (optional)",
            value=transaction.description or "",
            key=f"edit_description_{transaction.id}",
        )
        submitted = st.form_submit_button("Save changes", type="primary")

    if submitted:
        try:
            updated = update_transaction(
                connection,
                transaction.id,
                transaction_date,
                amount,
                transaction_type,
                category.id,
                payment_method,
                description,
            )
        except (TransactionValidationError, SmartSpendDatabaseError) as error:
            _handle_error(error)
        else:
            st.success(
                f"Transaction #{updated.id} updated to "
                f"{format_paise_as_rupees(updated.amount_paise)}."
            )


def _delete_transaction(connection) -> None:
    st.subheader("Delete a transaction")
    records = list_transaction_history(connection)
    if not records:
        st.info("There are no transactions to delete.")
        return

    selected = st.selectbox(
        "Select transaction",
        records,
        format_func=lambda item: (
            f"#{item.transaction.id} · {_format_date(item.transaction.transaction_date)} · "
            f"{item.category_name} · {format_paise_as_rupees(item.transaction.amount_paise)}"
        ),
        key="delete_transaction_selection",
    )
    with st.form("delete_transaction_form"):
        confirmed = st.checkbox(
            f"I confirm deletion of transaction #{selected.transaction.id}",
            key=f"confirm_delete_{selected.transaction.id}",
        )
        submitted = st.form_submit_button("Delete transaction", type="primary")

    if submitted:
        if not confirmed:
            st.warning("Confirm the deletion before continuing.")
            return
        try:
            delete_transaction(connection, selected.transaction.id)
        except SmartSpendDatabaseError as error:
            _handle_error(error)
        else:
            st.success(f"Transaction #{selected.transaction.id} deleted.")


def render_transactions_page(database_path) -> None:
    """Render add, history, edit, and confirmed-delete transaction workflows."""
    st.title("Transactions")
    st.caption("Record and manage income and expenses in your local database.")
    try:
        with open_connection(database_path) as connection:
            add_tab, history_tab, edit_tab, delete_tab = st.tabs(
                ("Add transaction", "History", "Edit", "Delete")
            )
            with add_tab:
                _add_transaction(connection)
            with history_tab:
                _transaction_history(connection)
            with edit_tab:
                _edit_transaction(connection)
            with delete_tab:
                _delete_transaction(connection)
    except SmartSpendDatabaseError as error:
        _handle_error(error)
