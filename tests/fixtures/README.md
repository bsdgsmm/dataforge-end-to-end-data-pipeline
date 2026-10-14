# Test fixtures

`source_small/` is a hand-built dataset whose expected metrics are calculated by hand and
asserted in `tests/integration/test_dbt_models.py`:

| Order | Customer | Status | Gross | Discount | Net sales | Refunds | Net revenue |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| ORD-0000001 | CUS-000001 | delivered | 120.00 | 10.00 | 110.00 | 20.00 | 90.00 |
| ORD-0000002 | CUS-000001 | shipped | 100.00 | 0.00 | 100.00 | 0.00 | 100.00 |
| ORD-0000003 | CUS-000002 | cancelled | 10.00 | 0.00 | 10.00 | 10.00 | 0 (not eligible) |
| ORD-0000004 | CUS-000002 | pending | 30.00 | 3.00 | 27.00 | 0.00 | 0 (not eligible) |
| ORD-0000005 | CUS-000002 | delivered | 10.00 | 0.00 | 10.00 | 10.00 | 0.00 |

Revenue-eligible totals: gross sales 230.00, discounts 10.00, net sales 220.00,
refunds 30.00, net revenue 190.00. Some values contain stray whitespace and mixed case
on purpose so that staging normalization is exercised.
