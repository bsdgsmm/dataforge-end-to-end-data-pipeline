"""Source data contracts shared by the generator, validator, and loader."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ColumnType(StrEnum):
    TEXT = "text"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    TIMESTAMP = "timestamp"


@dataclass(frozen=True)
class Column:
    name: str
    type: ColumnType
    required: bool = True
    accepted_values: frozenset[str] | None = None
    min_value: float | None = None
    exclusive_min: bool = False


@dataclass(frozen=True)
class ForeignKey:
    column: str
    parent_entity: str
    parent_column: str


@dataclass(frozen=True)
class SourceContract:
    entity: str
    file_name: str
    primary_key: str
    columns: tuple[Column, ...]
    foreign_keys: tuple[ForeignKey, ...] = field(default_factory=tuple)

    @property
    def column_names(self) -> list[str]:
        return [column.name for column in self.columns]

    def column(self, name: str) -> Column:
        for column in self.columns:
            if column.name == name:
                return column
        raise KeyError(f"{self.entity} has no column {name!r}")


ORDER_STATUSES = frozenset({"pending", "processing", "shipped", "delivered", "cancelled"})
REVENUE_ELIGIBLE_ORDER_STATUSES = frozenset({"processing", "shipped", "delivered"})
PAYMENT_METHODS = frozenset({"credit_card", "debit_card", "paypal", "bank_transfer", "gift_card"})
PAYMENT_STATUSES = frozenset({"pending", "succeeded", "failed"})
TRANSACTION_TYPES = frozenset({"charge", "refund"})

CUSTOMERS = SourceContract(
    entity="customers",
    file_name="customers.csv",
    primary_key="customer_id",
    columns=(
        Column("customer_id", ColumnType.TEXT),
        Column("email", ColumnType.TEXT),
        Column("first_name", ColumnType.TEXT),
        Column("last_name", ColumnType.TEXT),
        Column("country_code", ColumnType.TEXT),
        Column("city", ColumnType.TEXT, required=False),
        Column("signed_up_at", ColumnType.TIMESTAMP),
    ),
)

PRODUCTS = SourceContract(
    entity="products",
    file_name="products.csv",
    primary_key="product_id",
    columns=(
        Column("product_id", ColumnType.TEXT),
        Column("sku", ColumnType.TEXT),
        Column("product_name", ColumnType.TEXT),
        Column("category", ColumnType.TEXT),
        Column("list_price", ColumnType.DECIMAL, min_value=0),
        Column("is_active", ColumnType.BOOLEAN),
        Column("created_at", ColumnType.TIMESTAMP),
    ),
)

ORDERS = SourceContract(
    entity="orders",
    file_name="orders.csv",
    primary_key="order_id",
    columns=(
        Column("order_id", ColumnType.TEXT),
        Column("customer_id", ColumnType.TEXT),
        Column("order_status", ColumnType.TEXT, accepted_values=ORDER_STATUSES),
        Column("ordered_at", ColumnType.TIMESTAMP),
        Column("updated_at", ColumnType.TIMESTAMP),
        Column("currency", ColumnType.TEXT, accepted_values=frozenset({"USD"})),
    ),
    foreign_keys=(ForeignKey("customer_id", "customers", "customer_id"),),
)

ORDER_ITEMS = SourceContract(
    entity="order_items",
    file_name="order_items.csv",
    primary_key="order_item_id",
    columns=(
        Column("order_item_id", ColumnType.TEXT),
        Column("order_id", ColumnType.TEXT),
        Column("line_number", ColumnType.INTEGER, min_value=1),
        Column("product_id", ColumnType.TEXT),
        Column("quantity", ColumnType.INTEGER, min_value=0, exclusive_min=True),
        Column("unit_price", ColumnType.DECIMAL, min_value=0),
        Column("discount_amount", ColumnType.DECIMAL, min_value=0),
    ),
    foreign_keys=(
        ForeignKey("order_id", "orders", "order_id"),
        ForeignKey("product_id", "products", "product_id"),
    ),
)

PAYMENTS = SourceContract(
    entity="payments",
    file_name="payments.csv",
    primary_key="payment_id",
    columns=(
        Column("payment_id", ColumnType.TEXT),
        Column("order_id", ColumnType.TEXT),
        Column("transaction_type", ColumnType.TEXT, accepted_values=TRANSACTION_TYPES),
        Column("payment_method", ColumnType.TEXT, accepted_values=PAYMENT_METHODS),
        Column("payment_status", ColumnType.TEXT, accepted_values=PAYMENT_STATUSES),
        Column("amount", ColumnType.DECIMAL, min_value=0, exclusive_min=True),
        Column("created_at", ColumnType.TIMESTAMP),
    ),
    foreign_keys=(ForeignKey("order_id", "orders", "order_id"),),
)

# Ordered so that every parent entity precedes its children.
CONTRACTS: tuple[SourceContract, ...] = (CUSTOMERS, PRODUCTS, ORDERS, ORDER_ITEMS, PAYMENTS)
CONTRACTS_BY_ENTITY: dict[str, SourceContract] = {c.entity: c for c in CONTRACTS}
