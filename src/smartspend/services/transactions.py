"""Transaction validation, rupee conversion, and history filtering."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import TypeAlias

from smartspend.db.models import Category, Transaction
from smartspend.repositories.categories import get_category, list_categories
from smartspend.repositories.transactions import (
    create_transaction as repository_create_transaction,
)
from smartspend.repositories.transactions import (
    delete_transaction as repository_delete_transaction,
)
from smartspend.repositories.transactions import (
    list_transactions as repository_list_transactions,
)
from smartspend.repositories.transactions import (
    update_transaction as repository_update_transaction,
)

RupeeAmount: TypeAlias = str | Decimal | int | float
TRANSACTION_TYPES = ("income", "expense")
MAX_SQLITE_INTEGER = 9_223_372_036_854_775_807


class TransactionValidationError(ValueError):
    """Raised when transaction data fails application validation."""


@dataclass(frozen=True, slots=True)
class TransactionHistoryItem:
    transaction: Transaction
    category_name: str


def rupees_to_paise(amount: RupeeAmount) -> int:
    """Convert a positive rupee amount to exact integer paise."""
    if isinstance(amount, bool):
        raise TransactionValidationError("Enter a valid amount in rupees.")
    try:
        value = Decimal(str(amount).strip())
    except (InvalidOperation, ValueError):
        raise TransactionValidationError("Enter a valid amount in rupees.") from None

    if not value.is_finite() or value <= 0:
        raise TransactionValidationError("Amount must be greater than zero.")

    paise = value * 100
    if paise != paise.to_integral_value():
        raise TransactionValidationError("Amount can have at most two decimal places.")
    if paise > MAX_SQLITE_INTEGER:
        raise TransactionValidationError("Amount is too large to store.")
    return int(paise)


def _normalize_date(transaction_date: date | str) -> str:
    if isinstance(transaction_date, datetime):
        raise TransactionValidationError("Select a valid transaction date without a time.")
    if isinstance(transaction_date, date):
        return transaction_date.isoformat()
    if not isinstance(transaction_date, str):
        raise TransactionValidationError("Select a valid transaction date.")

    try:
        parsed_date = date.fromisoformat(transaction_date.strip())
    except ValueError:
        raise TransactionValidationError("Enter a valid transaction date.") from None
    if parsed_date.isoformat() != transaction_date.strip():
        raise TransactionValidationError("Enter the date in YYYY-MM-DD format.")
    return parsed_date.isoformat()


def _validated_fields(
    connection,
    transaction_date: date | str,
    amount: RupeeAmount,
    transaction_type: str,
    category_id: int,
    payment_method: str,
    description: str | None,
) -> tuple[str, int, str, int, str | None, str]:
    normalized_date = _normalize_date(transaction_date)
    amount_paise = rupees_to_paise(amount)
    if transaction_type not in TRANSACTION_TYPES:
        raise TransactionValidationError("Choose Income or Expense.")
    if isinstance(category_id, bool) or not isinstance(category_id, int) or category_id < 1:
        raise TransactionValidationError("Choose a valid category.")

    category = get_category(connection, category_id)
    if category is None:
        raise TransactionValidationError("The selected category no longer exists.")
    if category.category_type != transaction_type:
        raise TransactionValidationError("Choose a category matching the transaction type.")

    if not isinstance(payment_method, str) or not payment_method.strip():
        raise TransactionValidationError("Payment method is required.")
    if description is not None and not isinstance(description, str):
        raise TransactionValidationError("Description must be text.")

    normalized_description = description.strip() if description and description.strip() else None
    return (
        normalized_date,
        amount_paise,
        transaction_type,
        category_id,
        normalized_description,
        payment_method.strip(),
    )


def create_transaction(
    connection,
    transaction_date: date | str,
    amount: RupeeAmount,
    transaction_type: str,
    category_id: int,
    payment_method: str,
    description: str | None = None,
) -> Transaction:
    """Validate form input, convert rupees to paise, and create a transaction."""
    fields = _validated_fields(
        connection,
        transaction_date,
        amount,
        transaction_type,
        category_id,
        payment_method,
        description,
    )
    normalized_date, amount_paise, kind, category, detail, method = fields
    return repository_create_transaction(
        connection,
        normalized_date,
        amount_paise,
        kind,
        category,
        detail,
        method,
    )


def update_transaction(
    connection,
    transaction_id: int,
    transaction_date: date | str,
    amount: RupeeAmount,
    transaction_type: str,
    category_id: int,
    payment_method: str,
    description: str | None = None,
) -> Transaction:
    """Validate form input, convert rupees to paise, and update a transaction."""
    fields = _validated_fields(
        connection,
        transaction_date,
        amount,
        transaction_type,
        category_id,
        payment_method,
        description,
    )
    normalized_date, amount_paise, kind, category, detail, method = fields
    return repository_update_transaction(
        connection,
        transaction_id,
        normalized_date,
        amount_paise,
        kind,
        category,
        detail,
        method,
    )


def delete_transaction(connection, transaction_id: int) -> None:
    """Delete an existing transaction using the repository."""
    repository_delete_transaction(connection, transaction_id)


def list_transaction_history(
    connection,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    transaction_type: str | None = None,
    category_id: int | None = None,
    description_search: str | None = None,
) -> list[TransactionHistoryItem]:
    """Return transaction history filtered by date, type, category, and description."""
    normalized_start = _normalize_date(start_date) if start_date is not None else None
    normalized_end = _normalize_date(end_date) if end_date is not None else None
    if normalized_start and normalized_end and normalized_start > normalized_end:
        raise TransactionValidationError("Start date must not be after end date.")
    if transaction_type not in (None, *TRANSACTION_TYPES):
        raise TransactionValidationError("Choose a valid transaction type filter.")

    categories = {category.id: category for category in list_categories(connection)}
    search = description_search.strip().casefold() if description_search else ""
    history = []
    for transaction in repository_list_transactions(connection):
        category: Category | None = categories.get(transaction.category_id)
        if category is None:
            continue
        if normalized_start and transaction.transaction_date < normalized_start:
            continue
        if normalized_end and transaction.transaction_date > normalized_end:
            continue
        if transaction_type and transaction.transaction_type != transaction_type:
            continue
        if category_id is not None and transaction.category_id != category_id:
            continue
        if search and search not in (transaction.description or "").casefold():
            continue
        history.append(TransactionHistoryItem(transaction, category.name))
    return history


def categories_for_type(connection, transaction_type: str | None) -> list[Category]:
    """Return categories available for a validated income/expense selection."""
    if transaction_type is not None and transaction_type not in TRANSACTION_TYPES:
        raise TransactionValidationError("Choose Income or Expense.")
    return list_categories(connection, transaction_type)


def format_paise_as_rupees(amount_paise: int) -> str:
    """Format integer paise as an Indian rupee value with two decimal places."""
    sign = "-" if amount_paise < 0 else ""
    rupees, paise = divmod(abs(amount_paise), 100)
    number = str(rupees)
    if len(number) > 3:
        last_three = number[-3:]
        leading = number[:-3]
        groups = []
        while leading:
            groups.append(leading[-2:])
            leading = leading[:-2]
        number = ",".join(reversed(groups)) + "," + last_three
    return f"{sign}₹{number}.{paise:02d}"
