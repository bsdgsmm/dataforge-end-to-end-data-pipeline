"""Deterministic synthetic marketplace data.

All records are fictional. Emails use reserved example domains (RFC 2606).
The same seed and parameters always produce byte-identical CSV files.
"""

from __future__ import annotations

import csv
import logging
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from dataforge.contracts import CONTRACTS, CONTRACTS_BY_ENTITY

logger = logging.getLogger(__name__)

TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
CENT = Decimal("0.01")

DEFAULT_SEED = 42
PERIOD_START = datetime(2025, 1, 1, tzinfo=UTC)
PERIOD_END = datetime(2026, 1, 1, tzinfo=UTC)

CATEGORIES: dict[str, tuple[tuple[str, ...], tuple[int, int]]] = {
    "Electronics": (
        (
            "Wireless Earbuds",
            "Bluetooth Speaker",
            "USB-C Hub",
            "Smart Watch",
            "Power Bank",
            "HD Webcam",
            "Mechanical Keyboard",
            "Gaming Mouse",
        ),
        (19, 249),
    ),
    "Home & Kitchen": (
        (
            "Chef Knife",
            "French Press",
            "Cast Iron Skillet",
            "Glass Food Containers",
            "Electric Kettle",
            "Bamboo Cutting Board",
            "Stand Mixer",
            "Linen Towels",
        ),
        (12, 189),
    ),
    "Books": (
        (
            "Data Engineering Handbook",
            "Mystery Novel",
            "Travel Guide",
            "Cookbook",
            "Science Fiction Anthology",
            "Biography",
            "Poetry Collection",
            "Atlas",
        ),
        (8, 45),
    ),
    "Sports & Outdoors": (
        (
            "Yoga Mat",
            "Trail Running Shoes",
            "Insulated Water Bottle",
            "Camping Lantern",
            "Resistance Bands",
            "Hiking Backpack",
            "Cycling Gloves",
            "Foam Roller",
        ),
        (10, 160),
    ),
    "Beauty & Personal Care": (
        (
            "Face Moisturizer",
            "Hair Dryer",
            "Electric Toothbrush",
            "Sunscreen SPF 50",
            "Beard Trimmer",
            "Body Lotion",
            "Shampoo Bar",
            "Makeup Brush Set",
        ),
        (6, 95),
    ),
    "Toys & Games": (
        (
            "Building Blocks Set",
            "Puzzle 1000 Pieces",
            "Board Game",
            "Plush Bear",
            "Remote Control Car",
            "Card Game",
            "Science Kit",
            "Wooden Train Set",
        ),
        (9, 120),
    ),
    "Clothing": (
        (
            "Cotton T-Shirt",
            "Denim Jacket",
            "Wool Socks",
            "Rain Jacket",
            "Running Shorts",
            "Knit Sweater",
            "Canvas Sneakers",
            "Baseball Cap",
        ),
        (9, 140),
    ),
    "Office Supplies": (
        (
            "Notebook Set",
            "Gel Pens",
            "Desk Organizer",
            "Ergonomic Chair Cushion",
            "Monitor Stand",
            "Sticky Notes",
            "Laptop Sleeve",
            "Desk Lamp",
        ),
        (4, 85),
    ),
}

BRANDS = (
    "Nova",
    "Atlas",
    "Lumen",
    "Pioneer",
    "Orbit",
    "Summit",
    "Harbor",
    "Vertex",
    "Willow",
    "Ember",
    "Cobalt",
    "Juniper",
)

FIRST_NAMES = (
    "Ava",
    "Liam",
    "Mia",
    "Noah",
    "Zoe",
    "Ethan",
    "Ivy",
    "Lucas",
    "Nora",
    "Omar",
    "Sara",
    "Mateo",
    "Leah",
    "Arjun",
    "Elif",
    "Hana",
    "Jonas",
    "Clara",
    "Diego",
    "Amara",
    "Felix",
    "Yuki",
    "Priya",
    "Kenji",
    "Lina",
    "Tomas",
    "Ines",
    "Ravi",
    "Maya",
    "Emil",
)
LAST_NAMES = (
    "Smith",
    "Garcia",
    "Muller",
    "Rossi",
    "Kim",
    "Nguyen",
    "Silva",
    "Cohen",
    "Novak",
    "Yilmaz",
    "Larsen",
    "Dubois",
    "Tanaka",
    "Patel",
    "Brown",
    "Lopez",
    "Fischer",
    "Costa",
    "Ahmed",
    "Jensen",
)
EMAIL_DOMAINS = ("example.com", "example.org", "example.net")

COUNTRIES: dict[str, tuple[int, tuple[str, ...]]] = {
    "US": (40, ("New York", "Austin", "Seattle", "Chicago", "Denver")),
    "GB": (12, ("London", "Manchester", "Bristol")),
    "DE": (12, ("Berlin", "Hamburg", "Munich")),
    "FR": (8, ("Paris", "Lyon")),
    "NL": (6, ("Amsterdam", "Utrecht")),
    "TR": (8, ("Istanbul", "Izmir", "Ankara")),
    "CA": (8, ("Toronto", "Vancouver")),
    "ES": (6, ("Madrid", "Barcelona")),
}

PAYMENT_METHOD_WEIGHTS = {
    "credit_card": 52,
    "debit_card": 20,
    "paypal": 18,
    "bank_transfer": 6,
    "gift_card": 4,
}

MONTH_WEIGHTS = {
    1: 0.85,
    2: 0.8,
    3: 0.9,
    4: 0.9,
    5: 0.95,
    6: 0.95,
    7: 0.9,
    8: 0.9,
    9: 1.0,
    10: 1.05,
    11: 1.45,
    12: 1.6,
}


@dataclass(frozen=True)
class GenerationParams:
    seed: int = DEFAULT_SEED
    customers: int = 1500
    products: int = 120
    inject_defects: bool = False


Record = dict[str, str]
Dataset = dict[str, list[Record]]


def _ts(value: datetime) -> str:
    return value.astimezone(UTC).strftime(TIMESTAMP_FORMAT)


def _money(value: Decimal) -> str:
    return str(value.quantize(CENT, rounding=ROUND_HALF_UP))


def _weighted_choice(rng: random.Random, weights: dict[str, float]) -> str:
    return rng.choices(list(weights), weights=list(weights.values()), k=1)[0]


def _random_timestamp(rng: random.Random, start: datetime, end: datetime) -> datetime:
    span = int((end - start).total_seconds())
    return start + timedelta(seconds=rng.randrange(max(span, 1)))


def _seasonal_timestamp(rng: random.Random, start: datetime, end: datetime) -> datetime:
    max_weight = max(MONTH_WEIGHTS.values()) * 1.15
    while True:
        candidate = _random_timestamp(rng, start, end)
        weight = MONTH_WEIGHTS[candidate.month] * (1.15 if candidate.weekday() >= 5 else 1.0)
        if rng.random() * max_weight <= weight:
            return candidate


def _generate_products(rng: random.Random, count: int) -> list[Record]:
    categories = list(CATEGORIES)
    products = []
    for index in range(1, count + 1):
        category = categories[(index - 1) % len(categories)]
        base_names, (low, high) = CATEGORIES[category]
        brand = rng.choice(BRANDS)
        base_name = rng.choice(base_names)
        price = Decimal(rng.uniform(low, high)).quantize(Decimal("1")) - Decimal("0.01")
        products.append(
            {
                "product_id": f"PRD-{index:05d}",
                "sku": f"{category[:3].upper()}-{brand[:3].upper()}-{index:05d}",
                "product_name": f"{brand} {base_name}",
                "category": category,
                "list_price": _money(price),
                "is_active": "false" if rng.random() < 0.05 else "true",
                "created_at": _ts(
                    _random_timestamp(rng, datetime(2023, 1, 1, tzinfo=UTC), PERIOD_START)
                ),
            }
        )
    return products


def _generate_customers(rng: random.Random, count: int) -> list[Record]:
    country_weights = {code: weight for code, (weight, _) in COUNTRIES.items()}
    customers = []
    for index in range(1, count + 1):
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        country = _weighted_choice(rng, country_weights)
        email = f"{first}.{last}{index}@{rng.choice(EMAIL_DOMAINS)}".lower()
        # Source systems are not perfectly clean; staging normalizes these.
        if rng.random() < 0.04:
            email = f" {email.capitalize()} "
        country_code = country.lower() if rng.random() < 0.03 else country
        customers.append(
            {
                "customer_id": f"CUS-{index:06d}",
                "email": email,
                "first_name": first,
                "last_name": last,
                "country_code": country_code,
                "city": "" if rng.random() < 0.05 else rng.choice(COUNTRIES[country][1]),
                "signed_up_at": _ts(
                    _random_timestamp(
                        rng, datetime(2024, 1, 1, tzinfo=UTC), datetime(2025, 12, 1, tzinfo=UTC)
                    )
                ),
            }
        )
    return customers


def _orders_for_customer(rng: random.Random) -> int:
    return rng.choices([0, 1, 2, 3, 4, 6, 9], weights=[8, 34, 20, 14, 11, 8, 5], k=1)[0]


def _order_status(rng: random.Random, ordered_at: datetime) -> str:
    if rng.random() < 0.05:
        return "cancelled"
    age = PERIOD_END - ordered_at
    if age < timedelta(days=2):
        return "pending" if rng.random() < 0.4 else "processing"
    if age < timedelta(days=7):
        return "processing" if rng.random() < 0.2 else "shipped"
    return "delivered"


def _status_updated_at(rng: random.Random, status: str, ordered_at: datetime) -> datetime:
    offsets = {
        "pending": timedelta(minutes=rng.randint(0, 5)),
        "processing": timedelta(hours=rng.randint(1, 20)),
        "shipped": timedelta(days=rng.randint(1, 3), hours=rng.randint(0, 23)),
        "delivered": timedelta(days=rng.randint(3, 7), hours=rng.randint(0, 23)),
        "cancelled": timedelta(hours=rng.randint(1, 48)),
    }
    return min(ordered_at + offsets[status], PERIOD_END - timedelta(seconds=1))


def _generate_order_items(
    rng: random.Random, order_id: str, products: list[Record], product_weights: list[float]
) -> list[Record]:
    line_count = rng.choices([1, 2, 3, 4, 5], weights=[45, 30, 15, 7, 3], k=1)[0]
    chosen: list[Record] = []
    while len(chosen) < line_count:
        product = rng.choices(products, weights=product_weights, k=1)[0]
        if product not in chosen:
            chosen.append(product)

    discount_rate = rng.choice([Decimal("0.10"), Decimal("0.15"), Decimal("0.20")])
    has_promotion = rng.random() < 0.2
    items = []
    for line_number, product in enumerate(chosen, start=1):
        quantity = rng.choices([1, 2, 3, 4], weights=[70, 20, 7, 3], k=1)[0]
        unit_price = Decimal(product["list_price"])
        if rng.random() < 0.1:
            unit_price = (unit_price * Decimal(str(rng.uniform(0.9, 1.05)))).quantize(CENT)
        discount = (unit_price * quantity * discount_rate) if has_promotion else Decimal(0)
        items.append(
            {
                "order_item_id": f"{order_id}-{line_number:02d}",
                "order_id": order_id,
                "line_number": str(line_number),
                "product_id": product["product_id"],
                "quantity": str(quantity),
                "unit_price": _money(unit_price),
                "discount_amount": _money(discount),
            }
        )
    return items


def _item_net(item: Record) -> Decimal:
    return Decimal(item["unit_price"]) * int(item["quantity"]) - Decimal(item["discount_amount"])


class _PaymentFactory:
    def __init__(self, rng: random.Random) -> None:
        self._rng = rng
        self._sequence = 0
        self.records: list[Record] = []

    def add(
        self,
        order_id: str,
        transaction_type: str,
        method: str,
        status: str,
        amount: Decimal,
        created_at: datetime,
    ) -> None:
        self._sequence += 1
        self.records.append(
            {
                "payment_id": f"PAY-{self._sequence:07d}",
                "order_id": order_id,
                "transaction_type": transaction_type,
                "payment_method": method,
                "payment_status": status,
                "amount": _money(amount),
                "created_at": _ts(min(created_at, PERIOD_END - timedelta(seconds=1))),
            }
        )

    def for_order(self, order: Record, items: list[Record]) -> None:
        rng = self._rng
        order_id = order["order_id"]
        status = order["order_status"]
        ordered_at = datetime.strptime(order["ordered_at"], TIMESTAMP_FORMAT).replace(tzinfo=UTC)
        updated_at = datetime.strptime(order["updated_at"], TIMESTAMP_FORMAT).replace(tzinfo=UTC)
        total = sum((_item_net(item) for item in items), Decimal(0)).quantize(CENT)
        method = _weighted_choice(rng, PAYMENT_METHOD_WEIGHTS)
        paid_at = ordered_at + timedelta(minutes=rng.randint(1, 30))

        if status == "pending":
            self.add(order_id, "charge", method, "pending", total, paid_at)
            return

        if status == "cancelled":
            if rng.random() < 0.5:
                self.add(order_id, "charge", method, "failed", total, paid_at)
            else:
                self.add(order_id, "charge", method, "succeeded", total, paid_at)
                self.add(order_id, "refund", method, "succeeded", total, updated_at)
            return

        if rng.random() < 0.04:
            self.add(order_id, "charge", method, "failed", total, paid_at)
            method = _weighted_choice(rng, PAYMENT_METHOD_WEIGHTS)
            paid_at += timedelta(minutes=rng.randint(2, 20))

        if total > Decimal(40) and rng.random() < 0.03:
            gift_part = (total * Decimal(str(rng.uniform(0.2, 0.5)))).quantize(CENT)
            self.add(order_id, "charge", "gift_card", "succeeded", gift_part, paid_at)
            self.add(order_id, "charge", method, "succeeded", total - gift_part, paid_at)
        else:
            self.add(order_id, "charge", method, "succeeded", total, paid_at)

        if status == "delivered" and rng.random() < 0.06:
            refund = total if rng.random() < 0.5 else _item_net(rng.choice(items))
            refunded_at = updated_at + timedelta(days=rng.randint(1, 14))
            self.add(order_id, "refund", method, "succeeded", refund.quantize(CENT), refunded_at)


def _inject_defects(dataset: Dataset) -> None:
    """Append known-invalid records so that quality checks have something to catch."""
    customers, products = dataset["customers"], dataset["products"]
    orders, items, payments = dataset["orders"], dataset["order_items"], dataset["payments"]

    customers.append(dict(customers[10]))
    products.append({**products[5], "list_price": "999.99"})

    customer_with_orders = orders[20]["customer_id"]
    for customer in customers:
        if customer["customer_id"] == customer_with_orders:
            customer["email"] = ""
    customers[30]["email"] = "not-an-email"

    template = orders[100]
    orders.append({**template, "order_id": "ORD-9999901", "customer_id": "CUS-999999"})
    items.append({**items[0], "order_item_id": "ORD-9999901-01", "order_id": "ORD-9999901"})
    orders[150]["order_status"] = "lost_in_transit"

    items[200]["quantity"] = "-2"
    items[300]["unit_price"] = "twelve"

    orphan_order_id = orders[400]["order_id"]
    dataset["order_items"] = [i for i in items if i["order_id"] != orphan_order_id]

    charge = next(
        p
        for p in payments[500:]
        if p["transaction_type"] == "charge" and p["payment_status"] == "succeeded"
    )
    charge["amount"] = _money(Decimal(charge["amount"]) + Decimal("5.00"))
    payments[600]["created_at"] = "2025-13-45T00:00:00Z"


def generate_dataset(params: GenerationParams | None = None) -> Dataset:
    params = params or GenerationParams()
    rng = random.Random(params.seed)  # noqa: S311 - reproducible synthetic data, not security
    products = _generate_products(rng, params.products)
    customers = _generate_customers(rng, params.customers)

    ranks = list(range(1, len(products) + 1))
    rng.shuffle(ranks)
    product_weights = [1 / rank**0.8 for rank in ranks]

    order_drafts: list[tuple[datetime, str]] = []
    for customer in customers:
        signed_up_at = datetime.strptime(customer["signed_up_at"], TIMESTAMP_FORMAT).replace(
            tzinfo=UTC
        )
        window_start = max(signed_up_at, PERIOD_START)
        for _ in range(_orders_for_customer(rng)):
            ordered_at = _seasonal_timestamp(rng, window_start, PERIOD_END)
            order_drafts.append((ordered_at, customer["customer_id"]))
    order_drafts.sort()

    orders: list[Record] = []
    order_items: list[Record] = []
    payment_factory = _PaymentFactory(rng)
    for index, (ordered_at, customer_id) in enumerate(order_drafts, start=1):
        order_id = f"ORD-{index:07d}"
        status = _order_status(rng, ordered_at)
        order = {
            "order_id": order_id,
            "customer_id": customer_id,
            "order_status": status,
            "ordered_at": _ts(ordered_at),
            "updated_at": _ts(_status_updated_at(rng, status, ordered_at)),
            "currency": "USD",
        }
        items = _generate_order_items(rng, order_id, products, product_weights)
        orders.append(order)
        order_items.extend(items)
        payment_factory.for_order(order, items)

    dataset: Dataset = {
        "customers": customers,
        "products": products,
        "orders": orders,
        "order_items": order_items,
        "payments": payment_factory.records,
    }
    if params.inject_defects:
        _inject_defects(dataset)
    return dataset


def write_dataset(dataset: Dataset, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written = {}
    for contract in CONTRACTS:
        path = output_dir / contract.file_name
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=contract.column_names, lineterminator="\n")
            writer.writeheader()
            writer.writerows(dataset[contract.entity])
        written[contract.entity] = path
        logger.info("Wrote %s rows to %s", len(dataset[contract.entity]), path)
    return written


def source_files_present(source_dir: Path) -> bool:
    return all((source_dir / c.file_name).is_file() for c in CONTRACTS_BY_ENTITY.values())
