# data/

Generated files only; the directory contents are git-ignored except this README.

| Path | Created by | Contents |
| --- | --- | --- |
| `source/` | `make generate-data`, or the DAG's `generate_sample_data` task | Five synthetic CSV extracts: customers, products, orders, order_items, payments. |
| `source_defects/` | `make generate-defects` | The same dataset with deliberately invalid records appended. |
| `reports/<run_id>/` | `dataforge quality-check` and `dataforge finalize` | `data_quality_report.json` and `data_quality_report.md`. |

**The data is synthetic.** It is produced by `src/dataforge/generation/synthetic.py` with a fixed
seed (42), so every run produces byte-identical files. Names are drawn from small fixed lists,
and email addresses use the reserved `example.com/.org/.net` domains. None of it describes
real customers, products, or transactions.

Default volume: 1,500 customers, 120 products, and 3,817 orders with 7,492 order lines and
4,352 payment transactions, placed between 2025-01-01 and 2025-12-31 (UTC). A small share of
values are deliberately messy (mixed case, padded whitespace, lowercase country codes) so that
staging normalization has real work to do.
