# Spree Product Importer

Standalone CLI extracted from `em-celery/tools/spree/product_importer.py`. Reads JSONL product files, applies filters, and uploads batches to Spree.

## Setup

```bash
cd /home/sky/src/spree-product-importer
python -m venv .venv
source .venv/bin/activate
pip install -e ../em-tasks -e ../product-validator -e .
cp config.sample.ini config.ini
```

## Configuration

Uses the same store database config as em-celery. Set one of:

- `SPREE_PRODUCT_IMPORTER_CONFIG` — path to an ini file
- `MWS_COLLECTOR_CONFIGURATION_PATH` — legacy env var (compatible with em-celery)
- `~/.em_celery/config.ini` — default location

Required section (MySQL, used by `em-tasks` / Peewee):

```ini
[store_db]
host = localhost
user = root
password = secret
name = store
```

Optional PostgreSQL section (SQLAlchemy):

```ini
[pg_db]
host = localhost
port = 5432
user = postgres
password = secret
name = spree
```

Or set a full URL via env var (overrides ini):

```bash
export PG_DATABASE_URL="postgresql+psycopg://postgres:secret@localhost:5432/spree"
```

In code:

```python
from sqlalchemy import text

from spree_product_importer.config import init_pg_db
from spree_product_importer.database import session_scope

init_pg_db()

with session_scope() as session:
    rows = session.execute(text("SELECT 1")).all()
```

## Usage

```bash
spree-product-importer --help

spree-product-importer \
  -s us \
  -m MERCHANT_ID \
  -v VENDOR_ID \
  -sl 1 \
  -sc 1 \
  ./products.jsonl
```

Or run as a module:

```bash
python -m spree_product_importer.product_importer -s us -m ... -v ... -sl 1 -sc 1 ./products.jsonl
```

## Options

| Flag | Description |
|------|-------------|
| `-s, --store_code` | Store code (required) |
| `-m, --merchant_id` | Google Merchant ID |
| `-v, --vendor_id` | Vendor ID |
| `-sl, --stock_location_id` | Spree stock location ID |
| `-sc, --shipping_category_id` | Spree shipping category ID |
| `-pl, --min_price` | Minimum price (default 15) |
| `-ph, --max_price` | Maximum price (default 300) |
| `-nb, --dont_filter_blacklist` | Skip blacklist filtering |
| `-nt, --dont_optimize_title` | Skip spray-word title cleanup |
| `-ne, --dont_require_english_title` | Allow non-English titles |
