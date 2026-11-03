"""Synthetic transactions for previews, tests, and local demonstrations."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

TransactionType = Literal["income", "expense"]


@dataclass(frozen=True, slots=True)
class DemoTransaction:
    """A synthetic transaction that is never written to the user's database."""

    transaction_date: date
    amount: Decimal
    transaction_type: TransactionType
    category: str
    description: str
    payment_method: str


DEMO_TRANSACTIONS = (
    DemoTransaction(
        date(2025, 11, 1), Decimal("4200.00"), "income", "Salary", "Monthly salary", "Bank transfer"
    ),
    DemoTransaction(
        date(2025, 11, 3), Decimal("78.50"), "expense", "Food", "Weekly groceries", "Card"
    ),
    DemoTransaction(
        date(2025, 11, 8), Decimal("32.00"), "expense", "Transportation", "Transit pass", "Card"
    ),
    DemoTransaction(
        date(2025, 12, 1), Decimal("4200.00"), "income", "Salary", "Monthly salary", "Bank transfer"
    ),
    DemoTransaction(date(2025, 12, 4), Decimal("95.25"), "expense", "Food", "Groceries", "Card"),
    DemoTransaction(
        date(2025, 12, 12),
        Decimal("140.00"),
        "expense",
        "Utilities",
        "Electricity bill",
        "Bank transfer",
    ),
    DemoTransaction(
        date(2026, 1, 1), Decimal("4200.00"), "income", "Salary", "Monthly salary", "Bank transfer"
    ),
    DemoTransaction(date(2026, 1, 6), Decimal("64.75"), "expense", "Food", "Groceries", "Card"),
    DemoTransaction(
        date(2026, 1, 16), Decimal("48.00"), "expense", "Entertainment", "Cinema tickets", "Card"
    ),
    DemoTransaction(
        date(2026, 2, 1), Decimal("4200.00"), "income", "Salary", "Monthly salary", "Bank transfer"
    ),
    DemoTransaction(date(2026, 2, 5), Decimal("88.20"), "expense", "Food", "Groceries", "Card"),
    DemoTransaction(
        date(2026, 2, 10), Decimal("55.00"), "expense", "Transportation", "Fuel", "Card"
    ),
    DemoTransaction(
        date(2026, 3, 1), Decimal("4200.00"), "income", "Salary", "Monthly salary", "Bank transfer"
    ),
    DemoTransaction(date(2026, 3, 7), Decimal("102.40"), "expense", "Food", "Groceries", "Card"),
    DemoTransaction(
        date(2026, 3, 18), Decimal("210.00"), "expense", "Healthcare", "Clinic visit", "Card"
    ),
    DemoTransaction(
        date(2026, 4, 1), Decimal("4200.00"), "income", "Salary", "Monthly salary", "Bank transfer"
    ),
    DemoTransaction(date(2026, 4, 4), Decimal("91.60"), "expense", "Food", "Groceries", "Card"),
    DemoTransaction(
        date(2026, 4, 15), Decimal("65.00"), "expense", "Education", "Online course", "Card"
    ),
    DemoTransaction(
        date(2026, 5, 1), Decimal("4200.00"), "income", "Salary", "Monthly salary", "Bank transfer"
    ),
    DemoTransaction(date(2026, 5, 9), Decimal("110.30"), "expense", "Food", "Groceries", "Card"),
    DemoTransaction(
        date(2026, 5, 20), Decimal("75.00"), "expense", "Shopping", "Household items", "Card"
    ),
    DemoTransaction(
        date(2026, 6, 1), Decimal("4200.00"), "income", "Salary", "Monthly salary", "Bank transfer"
    ),
    DemoTransaction(date(2026, 6, 3), Decimal("97.80"), "expense", "Food", "Groceries", "Card"),
    DemoTransaction(
        date(2026, 6, 14),
        Decimal("142.00"),
        "expense",
        "Utilities",
        "Internet and phone",
        "Bank transfer",
    ),
    DemoTransaction(
        date(2026, 7, 1), Decimal("4200.00"), "income", "Salary", "Monthly salary", "Bank transfer"
    ),
    DemoTransaction(date(2026, 7, 6), Decimal("106.45"), "expense", "Food", "Groceries", "Card"),
    DemoTransaction(
        date(2026, 7, 21), Decimal("52.00"), "expense", "Transportation", "Transit pass", "Card"
    ),
    DemoTransaction(
        date(2026, 8, 1), Decimal("4200.00"), "income", "Salary", "Monthly salary", "Bank transfer"
    ),
    DemoTransaction(date(2026, 8, 5), Decimal("115.10"), "expense", "Food", "Groceries", "Card"),
    DemoTransaction(
        date(2026, 8, 17), Decimal("89.00"), "expense", "Entertainment", "Museum and lunch", "Card"
    ),
    DemoTransaction(
        date(2026, 9, 1), Decimal("4200.00"), "income", "Salary", "Monthly salary", "Bank transfer"
    ),
    DemoTransaction(date(2026, 9, 8), Decimal("99.95"), "expense", "Food", "Groceries", "Card"),
    DemoTransaction(
        date(2026, 9, 22), Decimal("180.00"), "expense", "Healthcare", "Dental check-up", "Card"
    ),
    DemoTransaction(
        date(2026, 10, 1), Decimal("4200.00"), "income", "Salary", "Monthly salary", "Bank transfer"
    ),
    DemoTransaction(date(2026, 10, 3), Decimal("108.75"), "expense", "Food", "Groceries", "Card"),
    DemoTransaction(
        date(2026, 10, 11), Decimal("68.00"), "expense", "Transportation", "Transit pass", "Card"
    ),
)
