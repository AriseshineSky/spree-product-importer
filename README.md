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

Vendor is **required by name** (`-vn`). Numeric `-v` / default vendor IDs
are not used. Config layout:

`[spree.import.{store}]` → shared defaults  
`[spree.import.{store}.{vendor_key}]` → vendor profile (`vendor_id`, sources)  
`[spree.import.{store}.{vendor_key}.{source}]` → per-source path / sl / sc

```bash
# TopSelected (vendor_id 24): all configured sources
uv run spree-product-importer -s em-spree -vn topselected

# One source only
uv run spree-product-importer -s em-spree -vn topselected -src amz_ca

# JP CMedia (vendor_id 42 / amz_jp)
uv run spree-product-importer -s em-spree -vn jp-cmedia
uv run spree-product-importer -s em-spree -vn "JP CMedia" -src amz_jp
uv run spree-product-importer -s em-spree -vn 42 -src amz_jp

# Ad-hoc file (uses vendor/source defaults; other CLI flags override)
uv run spree-product-importer -s em-spree -vn topselected -src amz_uk ./custom.jsonl
```

See `config.sample.ini` for full TopSelected + EM-HU + JP CMedia examples.

### EM-HU / AliExpress (vendor_id 62)

Run on **mongo** as `Admin` (`~/spree-product-importer`). Config:
`~/.em_celery/config.ini` → `[spree.import.em-spree.em-hu]`.

| Source | JSONL |
|--------|-------|
| `aliexpress` | `/home/Admin/em-tasks/data/aliexpress/aliexpress_to_upload.multi_variant.jsonl` |
| `inspireuplift` | `/home/Admin/em-tasks/data/inspireuplift/inspireuplift_to_upload.multi_variant.jsonl` |

Spray / perfume title filters are **skipped** for `aliexpress*` and
`inspireuplift` (`skip_spray_source_prefixes` /
`skip_perfume_source_prefixes` in config).

Single-SKU Aliexpress JSONL (same vendor settings, explicit path):

`/home/Admin/em-tasks/data/aliexpress/aliexpress_to_upload.jsonl`

```bash
cd ~/spree-product-importer

# All EM-HU sources (aliexpress → inspireuplift)
uv run spree-product-importer -s em-spree -vn em-hu

# AliExpress multi-variant (from prepare; default products_path)
uv run spree-product-importer -s em-spree -vn em-hu -src aliexpress

# AliExpress single-SKU
uv run spree-product-importer -s em-spree -vn em-hu -src aliexpress \
  /home/Admin/em-tasks/data/aliexpress/aliexpress_to_upload.jsonl

# InspireUplift only
uv run spree-product-importer -s em-spree -vn em-hu -src inspireuplift

# Nightly wrapper (flock + log under ~/logs/spree-import/)
./scripts/run_nightly_import.sh em-spree em-hu
```

### Nightly uploads (mongo, America/Chicago 23:00)

On **mongo** as `Admin` (`~/spree-product-importer`). One shell manages all
nightly jobs; cron calls that manager once at STL 11pm.

| Script | Role |
|--------|------|
| `scripts/run_nightly_uploads.sh` | Unified manager — edit `JOBS` list |
| `scripts/run_nightly_import.sh` | Single job: `store` `vendor` `[source]` |
| `deploy/crontab.example` | Cron template (`CRON_TZ=America/Chicago`) |

Default `JOBS` (Amazon; DE/JP omitted; NL = vendor 61 only):

| Vendor key | Source | vendor_id | sl | sc |
|------------|--------|-----------|----|----|
| `topselected` | `amz_ca` | 24 | 19 | 46901 |
| `topselected` | `amz_us` | 24 | 19 | 46865 |
| `topselected` | `amz_uk` | 24 | 41 | 46873 |
| `dubai-essence` | `amz_ae` | 49 | 57 | 46896 |
| `em-mx` | `amz_mx` | 50 | 58 | 46897 |
| `em-fr` | `amz_fr` | 57 | 65 | 46905 |
| `em-in` | `amz_in` | 52 | 60 | 46899 |
| `everymarket-it` | `amz_it` | 44 | 52 | 46889 |
| `em-pl` | `amz_pl` | 60 | 68 | 46908 |
| `em-nl` | `amz_nl` | 61 | 69 | 46909 |
| `em-horizon` | `amz_br` | 63 | 71 | 46911 |

JSONL: `/home/Admin/em-tasks/data/amazon/amz_{mp}_to_upload.jsonl`

```bash
cd ~/spree-product-importer

# Preview scheduled jobs
./scripts/run_nightly_uploads.sh --dry-run

# Run all configured Amazon jobs (same as cron)
./scripts/run_nightly_uploads.sh

# One marketplace
./scripts/run_nightly_import.sh em-spree topselected amz_us
./scripts/run_nightly_import.sh em-spree em-nl amz_nl
uv run spree-product-importer -s em-spree -vn em-mx -src amz_mx
```

Install cron on mongo:

```bash
crontab -e
# paste from deploy/crontab.example
# key line: 0 23 * * * .../scripts/run_nightly_uploads.sh
```

Logs: `~/logs/spree-import/nightly-uploads-YYYYMMDD.log` and per-job
`em-spree-*-amz_*-YYYYMMDD.log`.

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
| `-vn, --vendor` | Vendor profile name/key (required; e.g. topselected, em-hu) |
| `-src, --source` | Only one configured source name |
| `-m, --merchant_id` | Google Merchant ID (config default) |
| `-sl, --stock_location_id` | Spree stock location ID (per-source config) |
| `-sc, --shipping_category_id` | Spree shipping category ID (per-source config) |
| `-dl, --daily_upload_limit` | Max successful uploads/day (0=unlimited) |
| `-pl, --min_price` | Minimum price (default 15) |
| `-ph, --max_price` | Maximum price (default 300) |
| `-nb, --dont_filter_blacklist` | Skip blacklist filtering |
| `-ne, --dont_require_english_title` | Allow non-English titles for all sources |
| (config) `skip_english_title_source_prefixes` | Source prefixes that skip English-title check (e.g. `amz_`) |
| `-ap, --allow_perfume` | Allow perfume uploads (default: filtered) |
