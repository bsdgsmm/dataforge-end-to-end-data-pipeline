from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[1]
FIXTURES_DIR = Path(__file__).parent / "fixtures"
SMALL_SOURCE_DIR = FIXTURES_DIR / "source_small"
DBT_PROJECT_DIR = PROJECT_ROOT / "dbt" / "marketplace_analytics"
