"""Typed records returned by database repositories."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Category:
    id: int
    name: str
    category_type: str
    is_default: bool
    created_at: str
    updated_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "is_default", bool(self.is_default))


@dataclass(frozen=True, slots=True)
class Transaction:
    id: int
    transaction_date: str
    amount_paise: int
    transaction_type: str
    category_id: int
    description: str | None
    payment_method: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class Budget:
    id: int
    month: str
    amount_paise: int
    category_id: int | None
    created_at: str
    updated_at: str
