#!/usr/bin/env bash
# Nightly Spree import for one store_code (IDs/paths come from config.ini).
# Usage: run_nightly_import.sh em-spree
set -euo pipefail

STORE_CODE="${1:?store_code required, e.g. em-spree}"
VENDOR_ID="${2:-}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${HOME}/logs/spree-import"
LOCK_SUFFIX="${STORE_CODE}${VENDOR_ID:+-v${VENDOR_ID}}"
LOCK_FILE="/tmp/spree-import-${LOCK_SUFFIX}.lock"
mkdir -p "$LOG_DIR"

DAY="$(TZ=America/Chicago date +%Y%m%d)"
LOG_FILE="${LOG_DIR}/${LOCK_SUFFIX}-${DAY}.log"

export PATH="${HOME}/.local/bin:/usr/local/bin:${PATH}"

if ! command -v flock >/dev/null 2>&1; then
  echo "flock not found" | tee -a "$LOG_FILE"
  exit 1
fi

VENDOR_ARGS=""
if [[ -n "$VENDOR_ID" ]]; then
  VENDOR_ARGS="-v ${VENDOR_ID}"
fi

exec flock -n "$LOCK_FILE" bash -c "
  set -euo pipefail
  cd \"$ROOT\"
  {
    echo \"==== \$(date -Is) start store=${STORE_CODE} vendor=${VENDOR_ID:-default} ====\"
    uv run spree-product-importer -s \"$STORE_CODE\" ${VENDOR_ARGS}
    echo \"==== \$(date -Is) done store=${STORE_CODE} vendor=${VENDOR_ID:-default} ====\"
  } 2>&1 | tee -a \"$LOG_FILE\"
"
