from decimal import Decimal

from smartspend.demo_data import DEMO_TRANSACTIONS


def test_demo_transactions_are_synthetic_well_formed_records():
    assert len(DEMO_TRANSACTIONS) >= 12

    for transaction in DEMO_TRANSACTIONS:
        assert transaction.amount > Decimal("0")
        assert transaction.transaction_type in {"income", "expense"}
        assert transaction.category
        assert transaction.description
        assert transaction.payment_method


def test_demo_transactions_cover_more_than_one_month_and_both_types():
    months = {transaction.transaction_date.strftime("%Y-%m") for transaction in DEMO_TRANSACTIONS}
    transaction_types = {transaction.transaction_type for transaction in DEMO_TRANSACTIONS}

    assert len(months) >= 6
    assert transaction_types == {"income", "expense"}
