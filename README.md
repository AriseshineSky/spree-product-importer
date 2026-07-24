# Spree Product Importer

Standalone CLI extracted from `em-celery/tools/spree/product_importer.py`. Reads JSONL product files, applies filters, and uploads batches to Spree.

## Setup

```bash
cd /home/sky/src/spree-product-importer
uv sync
cp config.sample.ini config.ini
```

`em-tasks` and `product-validator` are local editable dependencies
(`../em-tasks`, `../product-validator`). `cmutils` is resolved from the
EveryMarket devpi index configured in `pyproject.toml`.

`em-tasks` dependencies from `requirements.txt` are listed explicitly in
this project because `uv` does not read `setup.py` install_requires.

Install dev tools (ruff):

```bash
uv sync --group dev
```

Common commands:

```bash
uv sync                  # install / update dependencies
uv lock                  # refresh lockfile after pyproject changes
uv run spree-product-importer --help
uv add package-name      # add a dependency
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

With `[spree.import.{store}]` configured (IDs + per-source paths), run:

```bash
# All configured sources for default vendor profile (TopSelected v24)
uv run spree-product-importer -s em-spree

# One source only
uv run spree-product-importer -s em-spree -src amz_ca

# Vendor profile (EM-HU v62: AliExpress + InspireUplift)
uv run spree-product-importer -s em-spree -v 62
uv run spree-product-importer -s em-spree -v 62 -src inspireuplift

# Ad-hoc file (still uses store/source defaults; CLI flags override)
uv run spree-product-importer -s em-spree -src amz_uk ./custom.jsonl
```

Equivalent TopSelected (vendor 24) config — CA / UK / eBay:

```ini
[spree.import.em-spree]
merchant_id = 654568556
vendor_id = 24
min_shipping_days = 10
min_price = 15
daily_upload_limit = 80000
quota_timezone = America/Chicago
sources = amz_ca, amz_uk, ebay_us

[spree.import.em-spree.amz_ca]
products_path = /home/Admin/em-tasks/data/amazon/amz_ca_to_upload.jsonl
stock_location_id = 19
shipping_category_id = 46901

[spree.import.em-spree.amz_uk]
products_path = /home/Admin/em-tasks/data/amazon/amz_uk_to_upload.jsonl
stock_location_id = 41
shipping_category_id = 46873

[spree.import.em-spree.ebay_us]
products_path = /home/Admin/em-tasks/data/ebay/ebay_us_to_upload.jsonl
stock_location_id = 19
shipping_category_id = 46862
```

Nightly cron (America/Chicago 23:00): see `deploy/crontab.example` and
`scripts/run_nightly_import.sh`.

Legacy one-shot (still works if you pass all IDs + a file path):

```bash
uv run spree-product-importer \
  -s em-spree \
  -m MERCHANT_ID \
  -v VENDOR_ID \
  -sl 1 \
  -sc 1 \
  ./products.jsonl
```

## Development

This project follows [PEP 8](https://peps.python.org/pep-0008/) (79-character line length).

```bash
uv sync --group dev
uv run ruff check spree_product_importer
uv run ruff format spree_product_importer
```

## Options

| Flag | Description |
|------|-------------|
| `-s, --store_code` | Store code (required) |
| `-src, --source` | Only one configured source name |
| `-m, --merchant_id` | Google Merchant ID (config default) |
| `-v, --vendor_id` | Vendor ID (config default) |
| `-sl, --stock_location_id` | Spree stock location ID (per-source config) |
| `-sc, --shipping_category_id` | Spree shipping category ID (per-source config) |
| `-dl, --daily_upload_limit` | Max successful uploads/day (0=unlimited) |
| `-pl, --min_price` | Minimum price (default 15) |
| `-ph, --max_price` | Maximum price (default 300) |
| `-nb, --dont_filter_blacklist` | Skip blacklist filtering |
| `-ne, --dont_require_english_title` | Allow non-English titles |
| `-ap, --allow_perfume` | Allow perfume uploads (default: filtered) |
